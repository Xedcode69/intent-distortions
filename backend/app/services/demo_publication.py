"""Publish an allowlisted, credential-free presentation of a verified replay."""
import json
from pathlib import Path
import sqlite3

from .canonical_data import canonical, sha
from .historical_replay import ReplayPlan, _load_capture
from .provenance import verify_artwork
from .randomness import round_for, select_timestamp, verify_beacon
from .storage import ContentStore


def publish_replay(report_path, destination):
    report_path = Path(report_path).resolve()
    directory = report_path.parent
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("mode") != "historical_replay" or report.get("status") != "passed":
        raise ValueError("Only a completed historical replay can become a public demo")
    required_tests = ("repeat_run_identical", "sample_membership_proofs", "tampered_record_rejected",
                      "tampered_artwork_commitment_rejected", "no_mint_or_auction")
    if any(report.get("tests", {}).get(name) is not True for name in required_tests):
        raise ValueError("The historical acceptance checks did not all pass")
    plan = ReplayPlan.build(report["plan"]["sunday"], report["plan"]["start"], report["plan"]["ai_policy"])
    if any(report["plan"].get(key) != value for key, value in plan.public().items()):
        raise ValueError("The recorded replay plan changed")
    evidence = json.loads((directory / "evidence.json").read_text(encoding="utf-8"))
    beacon = verify_beacon(evidence["beacon"], round_for(plan.sunday_start + 18 * 3600))
    target = select_timestamp(1, beacon["randomness"], plan.sunday_start)
    block = evidence["block"]
    if (evidence["selection"] != {"algorithm":"selection-v1", "sunday_start":plan.sunday_start, "selected_timestamp":target}
            or block.get("rpc_network") != "mainnet" or block.get("verified") is not True
            or not int(block["previous_timestamp_ns"]) < target * 10**9 <= int(block["timestamp_ns"])):
        raise ValueError("Saved checkpoint evidence does not match the selected timestamp")
    _, records, source = _load_capture(directory, plan, block)
    if not records:
        raise ValueError("A real nonempty capture is required")
    # Read-only SQLite access cannot initialize or modify production/replay state.
    with sqlite3.connect((directory / "replay.db").as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT payload FROM artworks WHERE id=?", (report["artwork"]["id"],)).fetchone()
    if row is None:
        raise ValueError("The frozen artwork is missing")
    artwork = json.loads(row[0])
    store = ContentStore(directory / "content")
    verification = verify_artwork(store, artwork, rerender=True)
    provenance = json.loads(store.get(artwork["provenance"]["sha256"]))
    if (not verification["valid"] or provenance["data_classification"] != "authenticated_explorer_capture"
            or provenance["mode"] != "historical_replay" or provenance["source"] != {**source, "reconciled":True, "freeze_rule":plan.public()["status_policy"]}
            or provenance["block"] != block or provenance["beacon"] != beacon
            or provenance["snapshot"]["sha256"] != source["sha256"]
            or artwork["nft"]["status"] != "not_minted" or artwork["auction"]["status"] != "not_created"
            or any(report["artwork"][key] != artwork[key] for key in ("id", "image_hash", "seed", "merkle_root"))):
        raise ValueError("Replay, capture and artwork commitments disagree")

    # Never copy the raw capture, canonical per-record snapshot, database, report,
    # provider URLs, original provenance source metadata or environment files.
    files = {name:store.get(provenance["files"][name]["sha256"])
             for name in ("artwork.png", "artwork-manifest.json")}
    summary = {
        "schema":"echo-historical-demo-v1", "mode":"historical_replay",
        "sunday":plan.sunday, "captured_at":source["capture_completed_at"],
        "interval":{"start":plan.start, "end":source["end"], "end_ns":str(block["timestamp_ns"])},
        "artwork":{key:artwork[key] for key in ("title", "description", "composition", "ai_provider", "image_hash", "seed", "merkle_root")},
        "statistics":{key:artwork["stats"][key] for key in ("total_swaps", "unique_chains", "particle_count",
            "chains", "dominant_routes", "activity", "public_volume_usd", "volume_coverage")},
        "checkpoint":{key:block[key] for key in ("height", "hash", "timestamp_ns")},
        "beacon":{"round":beacon["round"], "released_at":beacon["released_at"], "randomness":beacon["randomness"]},
        "snapshot_sha256":source["sha256"], "provenance_sha256":artwork["provenance"]["sha256"],
        "verification":{"checks":verification["checks"], "scope":verification["scope"], "rerendered_before_publication":True},
        "status_policy":plan.public()["status_policy"], "nft_and_auction":"not_run",
    }
    hashes = {name:sha(data).hex() for name, data in files.items()}
    if "network_mapping" in artwork["stats"]:
        summary["statistics"]["network_mapping"]=artwork["stats"]["network_mapping"]
    if "visual_features" in artwork["stats"]:
        summary["statistics"]["visual_features"]={key:value for key,value in artwork["stats"]["visual_features"].items() if key not in ("nodes","routes")}
    if "family_selection" in provenance:
        summary["family_selection"]=provenance["family_selection"]
    edition = sha(canonical({"summary":summary, "files":hashes})).hex()
    summary["files"] = {name:{"url":f"/historical-demo/editions/{edition}/{name}", "sha256":digest}
                        for name, digest in hashes.items()}
    destination = Path(destination).resolve()
    edition_dir = destination / "editions" / edition
    edition_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        target_file = edition_dir / name
        if target_file.exists() and target_file.read_bytes() != data:
            raise ValueError("Published immutable demo file changed")
        target_file.write_bytes(data)
    # Replace the pointer only after all immutable assets are present.
    temporary = destination / "index.json.tmp"
    temporary.write_bytes(canonical(summary))
    temporary.replace(destination / "index.json")
    return summary
