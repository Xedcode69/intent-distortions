"""Isolated historical acceptance test; never signs or claims historical freeze status."""
import copy
import asyncio
from contextlib import contextmanager
import os
import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..config import Settings
from ..database import Base,Job
from .art_seed import GENESIS_HASH
from .canonical_data import canonical, sha, snapshot
from .epoch_manager import run_epoch
from .intents_collector import Collector
from .merkle import levels, proof_from_levels, root, verify
from .near_rpc import NearRPC
from .provenance import verify_artwork
from .randomness import fetch_beacon, round_for, select_timestamp, verify_beacon
from .storage import ContentStore
from .replay_progress import ProgressWriter


@dataclass(frozen=True)
class ReplayPlan:
    sunday_start: int
    start: int
    ai: str = "fallback"

    @classmethod
    def build(cls, sunday=None, start=None, ai="fallback", now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("Replay clock must have a timezone")
        now = now.astimezone(timezone.utc)
        if sunday:
            day = datetime.strptime(sunday, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day -= timedelta(days=(day.weekday() + 1) % 7)
            if now < day + timedelta(hours=18):
                day -= timedelta(days=7)
        if day.weekday() != 6:
            raise ValueError("The release date must be a Sunday in UTC")
        if now < day + timedelta(hours=18):
            raise ValueError("Choose a completed Sunday whose beacon has been released")
        lower = int((day - timedelta(days=7)).timestamp()) if start is None else int(start)
        if lower < 0 or lower >= int(day.timestamp()):
            raise ValueError("The replay start checkpoint must precede the selected Sunday")
        if ai not in ("fallback", "required"):
            raise ValueError("AI policy must be fallback or required")
        return cls(int(day.timestamp()), lower, ai)

    @property
    def sunday(self):
        return datetime.fromtimestamp(self.sunday_start, timezone.utc).strftime("%Y-%m-%d")

    @property
    def name(self):
        return f"{self.sunday}-from-{self.start}-{self.ai}"

    def public(self):
        return {
            "sunday": self.sunday, "sunday_start": self.sunday_start,
            "beacon_at": self.sunday_start + 18 * 3600,
            "expected_beacon_round": round_for(self.sunday_start + 18 * 3600),
            "start": self.start, "start_ns": str(self.start * 10**9),
            "epoch": 1, "ai_policy": self.ai,
            "boundary_policy": "first isolated replay edition; explicit genesis start to selected checkpoint",
            "status_policy": "SUCCESS observed at capture time; not reconstructed as-of the original freeze",
        }


@contextmanager
def replay_lock(path):
    """OS-owned lock, released on exit/crash; the lock file contains no data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b"0"); handle.flush()
    handle.seek(0)
    acquired = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise RuntimeError("Another historical test owns this workspace's replay lock") from None
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def readiness(plan, settings, cached_capture=False):
    missing = []
    if not settings.near_intents_partner_jwt and not cached_capture:
        missing.append("NEAR_INTENTS_PARTNER_JWT")
    if plan.ai == "required":
        if not settings.near_ai_api_key:
            missing.append("NEAR_AI_API_KEY")
        if not settings.near_ai_text_model:
            missing.append("NEAR_AI_TEXT_MODEL")
    return {"ready_for_replay": not missing, "ready_to_fetch": bool(settings.near_intents_partner_jwt),
            "cached_capture_available": cached_capture, "missing": missing,
            "art_direction": "live_near_ai_required" if plan.ai == "required" else "explicit_deterministic_fallback",
            "signing": "disabled; NFT and auction testing are separate"}


def _write(path, value):
    # Report metadata contains no secrets; source raw records remain in ignored data/.
    data = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def isolated_settings(base, directory, ai):
    values = base.model_dump()
    values.update(app_env="test", execution_mode="historical_replay", service_role="operator",
                  data_dir=directory, database_url=f"sqlite:///{(directory/'replay.db').as_posix()}",
                  storage_provider="local_content_addressed", scheduler_enabled=False,
                  enable_chain_writes=False, mainnet_writes_approved=False, signer_key_file="",
                  near_nft_contract="", near_auction_contract="", admin_token="", near_network="mainnet",
                  allow_ai_fallback=ai == "fallback")
    if ai == "fallback":
        values.update(near_ai_api_key="", near_ai_text_model="")
    return Settings(_env_file=None, **values)


def _load_capture(directory, plan, block):
    source = json.loads((directory / "capture.source.json").read_text(encoding="utf-8"))
    raw_bytes = (directory / "capture.raw.json").read_bytes()
    if sha(raw_bytes).hex() != source["raw_sha256"]:
        raise ValueError("Raw capture hash mismatch")
    if source.get("classification") != "authenticated_explorer_capture" or source.get("complete") is not True:
        raise ValueError("A complete authenticated Explorer capture is required")
    if source["start_ns"] != str(plan.start * 10**9) or source["end_ns"] != str(block["timestamp_ns"]):
        raise ValueError("Cached capture does not match the requested exact interval")
    expected_end = (int(block["timestamp_ns"]) + 10**9 - 1) // 10**9
    if source["start"] != plan.start or source["end"] != expected_end:
        raise ValueError("Cached capture seconds do not match exact checkpoint bounds")
    raw = json.loads(raw_bytes)
    if dict(Counter(row["status"] for row in raw)) != source["status_counts"]:
        raise ValueError("Capture status-count metadata mismatch")
    records = snapshot(raw, plan.start, source["end"], start_ns=plan.start * 10**9,
                       end_ns=int(block["timestamp_ns"]))
    encoded = canonical(records)
    if sha(encoded).hex() != source["sha256"] or encoded != (directory / "capture.snapshot.json").read_bytes():
        raise ValueError("Canonical capture commitment mismatch")
    return raw, records, source


def _preview_profile(directory):
    # Serving an already-rendered replay needs no integration keys or contracts.
    values = {"APP_ENV": "development", "EXECUTION_MODE": "historical_replay", "NEAR_NETWORK": "mainnet",
              "DATABASE_URL": f"sqlite:///{(directory/'replay.db').as_posix()}",
              "DATA_DIR": directory.as_posix(), "STORAGE_PROVIDER": "local_content_addressed",
              "SCHEDULER_ENABLED": "false", "ENABLE_CHAIN_WRITES": "false",
              "MAINNET_WRITES_APPROVED": "false", "ALLOW_AI_FALLBACK": "true",
              "NEAR_NFT_CONTRACT": "", "NEAR_AUCTION_CONTRACT": "",
              "NEAR_INTENTS_PARTNER_JWT": "", "NEAR_AI_API_KEY": "",
              "SIGNER_KEY_FILE": "", "ADMIN_TOKEN": ""}
    (directory / "preview.env").write_text("\n".join(f'{key}={json.dumps(value)}' for key, value in values.items()) + "\n", encoding="utf-8")


async def replay_week(plan, base, directory, *, action="run", rpc=None, collector=None,
                      beacon_fetch=None, clock=time.time, progress=lambda message: None):
    """Run/check/prepare one historical first-edition test in a separate directory.

    Dependencies can be replaced in unit tests. Only the CLI's normal providers
    establish live evidence; tests explicitly identify their mocks.
    """
    if action not in ("check", "prepare", "run"):
        raise ValueError("Unknown replay action")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    cfg = isolated_settings(base, directory, plan.ai)
    published_plan = {**plan.public(), "ai_model": cfg.near_ai_text_model or None}
    plan_file = directory / "plan.json"
    if plan_file.exists():
        previous_plan = json.loads(plan_file.read_text(encoding="utf-8"))
        # A readiness check or public checkpoint preparation must not prevent
        # configuring AI before any creative generation has initialized state.
        model_only_before_generation = (not (directory / "replay.db").exists()
            and {**previous_plan, "ai_model":published_plan["ai_model"]} == published_plan)
        if previous_plan != published_plan and not model_only_before_generation:
            raise ValueError("Replay inputs/model changed; use a separate output directory")
    if action != "check":
        _write(plan_file, published_plan)
    cached = all((directory / name).is_file() for name in ("capture.source.json", "capture.raw.json", "capture.snapshot.json"))
    requirements = readiness(plan, base, cached)
    report = {"schema": "echo-historical-test-v1", "mode": "historical_replay", "plan": published_plan,
              "status": "running", "requirements": requirements, "stages": {}, "tests": {},
              "nft_and_auction": "not_run; no signing or transfers requested", "full_live_acceptance": False,
              "limitations": ["Provider statuses are observed at capture time, not at the past Sunday freeze.",
                              "Merkle membership does not establish provider completeness.",
                              "The initial checkpoint is the explicitly recorded replay genesis.",
                              "Replay does not exercise the live scheduler or prove real NFT/auction execution."]}
    if action == "check":
        report["status"] = "ready" if requirements["ready_for_replay"] else "blocked"
        _write(directory / "readiness.json", report)
        return report

    tracker = ProgressWriter(directory, sunday=plan.sunday, start=plan.start, clock=clock)
    rpc = rpc or NearRPC(cfg.near_mainnet_rpc_url)
    fetch = beacon_fetch or fetch_beacon
    stage = "beacon"
    engine = None
    try:
        tracker.update(stage="beacon")
        progress("Verifying the predetermined historical drand beacon")
        beacon_file = directory / "beacon.json"
        beacon = json.loads(beacon_file.read_text(encoding="utf-8")) if beacon_file.exists() else await fetch(plan.sunday_start + 18 * 3600)
        beacon = verify_beacon(beacon, round_for(plan.sunday_start + 18 * 3600))
        _write(beacon_file, beacon)
        target = select_timestamp(1, beacon["randomness"], plan.sunday_start)
        report["stages"]["beacon"] = {"status": "passed", "round": beacon["round"], "selected_timestamp": target}

        stage = "checkpoint"
        tracker.update(stage=stage)
        progress("Checking the historical mainnet block, predecessor and finality")
        if (await asyncio.wait_for(rpc.call("status", {}),timeout=45))["chain_id"] != "mainnet":
            raise ValueError("Historical source RPC must be NEAR mainnet")
        evidence_file = directory / "evidence.json"
        if evidence_file.exists():
            evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
            if evidence["selection"] != {"algorithm": "selection-v1", "sunday_start": plan.sunday_start, "selected_timestamp": target}:
                raise ValueError("Cached checkpoint selection differs from the replay plan")
            if evidence["beacon"] != beacon:
                raise ValueError("Cached checkpoint beacon changed")
            block = evidence["block"]
        else:
            block = await rpc.first_block_at(target)
        await asyncio.wait_for(rpc.verify_selected_block(block, target),timeout=90)
        if int(block["timestamp_ns"]) <= plan.start * 10**9:
            raise ValueError("Selected checkpoint does not follow the replay start")
        evidence = {"block": block, "beacon": beacon, "selection": {
            "algorithm": "selection-v1", "sunday_start": plan.sunday_start, "selected_timestamp": target}}
        _write(evidence_file, evidence)
        report["stages"]["checkpoint"] = {"status": "passed", "height": block["height"], "hash": block["hash"], "timestamp_ns": str(block["timestamp_ns"])}
        report["interval"] = {"start_ns": str(plan.start * 10**9), "end_ns": str(block["timestamp_ns"]), "rule": "[start,end)"}
        tracker.update(end_ns=str(block["timestamp_ns"]))
        if action == "prepare":
            report["status"] = "checkpoint_prepared"
            return report

        stage = "capture"
        tracker.update(stage=stage)
        capture_file = directory / "capture.source.json"
        if not capture_file.exists():
            if (directory / "replay.db").exists():
                import sqlite3
                with sqlite3.connect((directory / "replay.db").as_uri() + "?mode=ro", uri=True) as db:
                    if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='epochs'").fetchone() and db.execute("SELECT 1 FROM epochs LIMIT 1").fetchone():
                        raise ValueError("Frozen replay requires its original capture; use a new directory for a new capture")
            if not base.near_intents_partner_jwt:
                report["status"] = "blocked"
                report["stages"][stage] = {"status": "blocked", "missing": ["NEAR_INTENTS_PARTNER_JWT"]}
                return report
            progress("Collecting SUCCESS-only authenticated Explorer pages; one request per five seconds")
            client = collector or Collector(base.near_intents_explorer_url, base.near_intents_partner_jwt)
            end = (int(block["timestamp_ns"]) + 10**9 - 1) // 10**9
            started = int(clock())
            pages = rows = 0
            last_progress = time.monotonic()
            def collected_page(page):
                nonlocal pages, rows, last_progress
                pages += 1; rows += len(page)
                tracker.update(pages=pages, received_rows=rows)
                if pages == 1 or time.monotonic() - last_progress >= 30:
                    progress(f"Explorer capture: {pages} pages, {rows} received rows; pagination continues until complete")
                    last_progress = time.monotonic()
            if collector is None:
                raw, source = await client.collect(plan.start, end, cfg.collector_page_size,
                                                  on_page=collected_page, statuses=("SUCCESS",))
            else:
                raw, source = await client.collect(plan.start, end, cfg.collector_page_size)
            if source.get("complete") is not True:
                raise ValueError("Incomplete Explorer capture cannot be replayed")
            records = snapshot(raw, plan.start, end, start_ns=plan.start * 10**9, end_ns=int(block["timestamp_ns"]))
            raw_bytes = (json.dumps(raw, ensure_ascii=False, allow_nan=False) + "\n").encode()
            (directory / "capture.raw.json").write_bytes(raw_bytes)
            (directory / "capture.snapshot.json").write_bytes(canonical(records))
            source = {**source, "classification": "authenticated_explorer_capture", "start": plan.start, "end": end,
                      "start_ns": str(plan.start * 10**9), "end_ns": str(block["timestamp_ns"]),
                      "sha256": sha(canonical(records)).hex(), "raw_sha256": sha(raw_bytes).hex(),
                      "capture_started_at": started, "capture_completed_at": int(clock()),
                      "status_counts": dict(Counter(row["status"] for row in raw)), "status_policy": plan.public()["status_policy"]}
            _write(capture_file, source)
        else:
            progress("Verifying and reusing the saved capture; no Explorer requests repeated")
        raw, records, source = _load_capture(directory, plan, block)
        tracker.update(pages=source.get("pages",0), received_rows=max(tracker.value.received_rows,len(raw)),
                       total_records=len(raw), eligible_records=len(records), collection_complete=True,
                       total_source="complete_capture")
        if not records:
            raise ValueError("No successful eligible records; this test requires a nonempty historical dataset")
        report["stages"][stage] = {"status": "passed", "raw_records": len(raw), "successful_records": len(records),
                                   "snapshot_sha256": source["sha256"], "status_counts": source["status_counts"],
                                   "observed_at": source["capture_completed_at"]}

        stage = "art_direction"
        tracker.update(stage=stage)
        if plan.ai == "required" and (not cfg.near_ai_api_key or not cfg.near_ai_text_model):
            report["status"] = "blocked"
            report["stages"][stage] = {"status": "blocked", "reason": "NEAR AI key and model ID required"}
            return report
        progress("Generating the isolated replay edition with the recorded AI policy")
        engine = create_engine(cfg.database_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        arguments = dict(number=1, mode="historical_replay", raw=raw, start=plan.start, end=source["end"],
                         start_ns=plan.start * 10**9, end_ns=int(block["timestamp_ns"]), block=block,
                         beacon=beacon, selection=evidence["selection"], previous_hash=GENESIS_HASH, evidence_rpc=rpc,
                         source={**source, "reconciled": True, "freeze_rule": plan.public()["status_policy"]})
        artwork = await run_epoch(factory, cfg, **arguments)
        report["stages"][stage] = {"status": "passed" if plan.ai == "required" else "fallback_selected", "provider": artwork["ai_provider"]}
        stage = "verification"
        tracker.update(stage=stage)
        progress("Rebuilding the scene and PNG; checking membership, idempotency and tamper detection")
        store = ContentStore(directory / "content")
        verification = verify_artwork(store, artwork, rerender=True)
        if not verification["valid"]:
            raise ValueError("Generated replay did not pass full integrity verification")
        second = await run_epoch(factory, cfg, **arguments)
        report["tests"]["repeat_run_identical"] = artwork == second
        tree = levels(records)
        expected_root = tree[-1][0].hex()
        indexes = sorted({0, len(records) // 2, len(records) - 1})
        report["tests"]["sample_membership_proofs"] = all(verify(records[i], proof_from_levels(tree, i), expected_root) for i in indexes)
        altered = copy.deepcopy(records[0])
        altered["amount_in_usd"] = "0" if altered["amount_in_usd"] != "0" else "1"
        report["tests"]["tampered_record_rejected"] = not verify(altered, proof_from_levels(tree, 0), expected_root)
        changed_seed = ("0" if artwork["seed"][0] != "0" else "1") + artwork["seed"][1:]
        report["tests"]["tampered_artwork_commitment_rejected"] = not verify_artwork(store, {**artwork, "seed": changed_seed})["valid"]
        report["tests"]["no_mint_or_auction"] = artwork["nft"]["status"] == "not_minted" and artwork["auction"]["status"] == "not_created"
        if not all(report["tests"].values()):
            raise ValueError("A historical replay acceptance assertion failed")
        report["stages"][stage] = verification

        stage = "export"
        tracker.update(stage=stage)
        provenance_bytes = store.get(artwork["provenance"]["sha256"])
        provenance = json.loads(provenance_bytes)
        export = directory / "export"
        export.mkdir(exist_ok=True)
        for name, ref in provenance["files"].items():
            if Path(name).name != name:
                raise ValueError("Invalid export filename")
            (export / name).write_bytes(store.get(ref["sha256"]))
        (export / "provenance.json").write_bytes(provenance_bytes)
        _preview_profile(directory)
        summary = {"mode": "historical_replay", "status": "replay_complete", "epoch_number": 1,
                   "indexed_records": len(records), "selected_block": block, "freeze_at": None,
                   "interval": {"start": plan.start, "end": source["end"]},
                   "captured_at": source["capture_completed_at"], "collection": "historical_capture_observed_at_capture_time",
                   "schedule_timezone": "UTC", "last_error_type": None,
                   "next_selection": {"window_start": plan.sunday_start, "window_end": plan.sunday_start + 17 * 3600,
                                      "beacon_at": plan.sunday_start + 18 * 3600}}
        with factory.begin() as db:
            job = db.get(Job, "historical-replay-summary")
            if job is None:
                db.add(Job(key="historical-replay-summary", kind="historical_replay", status="succeeded", attempts=1, payload=summary))
            else:
                job.payload = summary; job.status = "succeeded"; job.updated_at = int(clock())
        report["artwork"] = {"id": artwork["id"], "title": artwork["title"], "image_hash": artwork["image_hash"],
                             "seed": artwork["seed"], "merkle_root": artwork["merkle_root"], "statistics": artwork["stats"],
                             "image_file": str(export / "artwork.png"), "provenance_file": str(export / "provenance.json")}
        report["stages"][stage] = {"status": "passed", "directory": str(export)}
        report["status"] = "passed"
        return report
    except asyncio.CancelledError:
        report["status"] = "interrupted"
        report["stages"][stage] = {"status":"interrupted","hint":"Saved frozen inputs were retained; rerun the same command."}
        raise
    except Exception as exc:
        report["status"] = "failed"
        report["stages"][stage] = {"status": "failed", "error_type": type(exc).__name__,
                                   "hint": {"beacon": "Check the scheduled beacon and network connection.",
                                            "checkpoint": "A working archival mainnet RPC is required; no latest-block substitute is used.",
                                            "capture": "Check JWT access, full pagination, exact boundaries and saved capture integrity.",
                                            "art_direction": "Check the requested AI policy and funded model access.",
                                            "verification": "Inspect the saved dataset and artifact commitments; frozen data was not reset."}.get(stage, "Inspect the saved replay inputs.")}
        return report
    finally:
        if engine is not None:
            engine.dispose()
        tracker.update(status=report["status"] if report["status"] in ("passed","failed","blocked","interrupted") else "idle",
                       stage="complete" if report["status"] == "passed" else stage)
        _write(directory / "report.json", report)
        lines = ["# NEAR ECHOES historical replay test", "", f"Status: {report['status']}",
                 f"Sunday: {plan.sunday}; mode: historical_replay; AI policy: {plan.ai}", "",
                 "This run does not sign transactions or prove production as-of-freeze membership.", ""]
        for name, result in report["stages"].items():
            lines.append(f"- {name}: {result.get('status', 'passed' if result.get('valid') else 'unknown')}")
        if "artwork" in report:
            lines.extend(["", f"Image SHA-256: `{report['artwork']['image_hash']}`", "", "Artwork: [artwork.png](export/artwork.png)"])
        (directory / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
