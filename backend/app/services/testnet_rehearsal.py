"""Prepare/review an isolated testnet mint. Signed operations are explicit and journaled."""
import asyncio
import base64
import copy
import hashlib
import ipaddress
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import base58
import httpx
from pydantic_settings import DotEnvSettingsSource
from sqlalchemy import select

from ..config import Settings
from ..database import Artwork, init_db
from .canonical_data import canonical, sha
from .near_rpc import NearRPC
from .nft_traits import publish_traits, token_metadata
from .preflight import validate_contracts
from .provenance import verify_artwork
from .storage import ContentStore
from .testnet_profile import SCHEMA
from . import testnet_profile

ROOT = Path(__file__).resolve().parents[3]
FIRST_RELEASE = 1794700800
WEEK = 604800
ROLES = {"governance": "testnet_governance_account", "operator": "near_minter_account",
         "creator": "near_creator_account", "treasury": "near_treasury_account",
         "nft": "near_nft_contract", "auction": "near_auction_contract", "market": "near_market_contract"}
ARTIFACTS = {"nft": "echo_nft.wasm", "auction": "echo_auction.wasm", "vault": "echo_vault.wasm", "market": "echo_market.wasm"}
class RehearsalError(ValueError):
    """An operator-safe explanation without provider exception text."""


ACCOUNT = re.compile(r"^(?=.{2,64}$)[a-z0-9]+(?:[._-][a-z0-9]+)*$")


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical(value))
    os.replace(temporary, path)


def workspace(directory):
    directory = Path(directory).resolve()
    root = testnet_profile.REHEARSAL_ROOT.resolve()
    if directory == root or not directory.is_relative_to(root):
        raise RehearsalError("Choose a workspace inside data/testnet-rehearsals")
    if json.loads((directory / "prepared.json").read_text(encoding="utf-8")).get("schema") != SCHEMA:
        raise RehearsalError("Not a prepared testnet rehearsal")
    return directory


def load_settings(directory):
    directory = workspace(directory)
    # Explicit values for every field keep ambient production environment variables
    # and .env credentials out of this operator workflow.
    values = {name: field.get_default(call_default_factory=True) for name, field in Settings.model_fields.items()}
    values.update(DotEnvSettingsSource(Settings, env_file=directory / "profile.env", env_file_encoding="utf-8")())
    result = Settings(_env_file=None, **values)
    if result.execution_mode != "testnet_rehearsal" or result.testnet_rehearsal_dir.resolve() != directory:
        raise RehearsalError("Use the prepared testnet-only profile")
    return result


@contextmanager
def operator_lock(directory):
    path = workspace(directory) / "operator.lock"
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise RehearsalError("An operator command is running; inspect operator.lock before recovery") from None
    try:
        handle.write(str(os.getpid())); handle.close()
        yield
    finally:
        path.unlink(missing_ok=True)


def build_hashes(lab=False):
    result = {}
    for role, name in ARTIFACTS.items():
        path = wasm_directory(lab) / name
        if not path.is_file():
            raise RehearsalError("Build current WASM first: uv run --locked python scripts/build_contracts.py --test")
        result[role] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _safe_public_document(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"private_key", "api_key", "authorization", "partner_jwt", "rpc_url", "headers"}:
                raise RehearsalError("Private provider information cannot be exported")
            _safe_public_document(child)
    elif isinstance(value, list):
        for child in value:
            _safe_public_document(child)
    elif isinstance(value, str) and value.startswith(("https://", "http://")):
        parsed = urlsplit(value)
        if parsed.username or parsed.password or parsed.query:
            raise RehearsalError("Credential-bearing URLs cannot be exported")


def prepare(report_path, name, lab=False):
    report_path = Path(report_path).resolve()
    sources = (ROOT / "data/replays").resolve()
    if not report_path.is_relative_to(sources) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name):
        raise RehearsalError("Choose a saved replay report and a short lowercase workspace name")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "passed" or report.get("mode") != "historical_replay":
        raise RehearsalError("The source replay must have passed verification")
    directory = testnet_profile.REHEARSAL_ROOT / name
    directory.parent.mkdir(parents=True, exist_ok=True)
    if directory.exists():
        raise RehearsalError("Workspace already exists; reuse it or choose a new name")
    directory = directory.resolve()
    if not directory.is_relative_to(testnet_profile.REHEARSAL_ROOT.resolve()):
        raise RehearsalError("Workspace path escaped its root")
    source = report_path.parent
    database = source / "replay.db"
    if not database.is_file() or not (source / "content").is_dir():
        raise RehearsalError("Replay database/content is missing")
    hashes = build_hashes(lab)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    source_store = ContentStore(source / "content")
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute("SELECT payload FROM artworks").fetchall()
    artworks = [json.loads(row["payload"]) for row in rows]
    artworks = [art for art in artworks if art["mode"] == "historical_replay"]
    if len(artworks) != 1 or artworks[0]["number"] not in (1, 2, 3):
        connection.close()
        raise RehearsalError("Mint-only rehearsal requires one saved creator-period artwork")
    art = artworks[0]
    if not verify_artwork(source_store, art, True)["valid"]:
        connection.close()
        raise RehearsalError("Source artwork failed verification")
    # A fresh directory is never reused after incomplete preparation.
    directory.mkdir()
    try:
        with sqlite3.connect(directory / "rehearsal.db") as target:
            connection.backup(target)
    finally:
        connection.close()
    provenance = json.loads(source_store.get(art["provenance"]["sha256"]))
    target_store = ContentStore(directory / "content")
    refs = [art["provenance"], provenance["snapshot"], *provenance["files"].values()]
    for ref in refs:
        target_store.put(source_store.get(ref["sha256"]))
    if not verify_artwork(target_store, art, True)["valid"]:
        raise RehearsalError("Copied artwork failed verification")
    traits, ref = publish_traits(target_store, art)
    public = directory / "public"
    public.mkdir()
    _safe_public_document(provenance)
    files = {"provenance.json": art["provenance"]["sha256"], "nft-traits.json": ref["sha256"]}
    for filename in ("artwork.png", "artwork.svg", "thumbnail.webp", "artwork-manifest.json"):
        if filename in provenance["files"]:
            files[filename] = provenance["files"][filename]["sha256"]
    for filename, digest in files.items():
        (public / filename).write_bytes(target_store.get(digest))
    write_json(public / "publish-manifest.json", {"schema": SCHEMA, "files": files,
               "notice": "Testnet historical-art rehearsal. No raw capture or snapshot is included."})
    manifest = {"schema": SCHEMA, "source_mode": "historical_replay", "source_report_sha256": sha(report_path.read_bytes()).hex(),
                "source_database_sha256": before, "artwork_id": art["id"], "image_sha256": art["image_hash"],
                "provenance_sha256": art["provenance"]["sha256"], "trait_sha256": traits["sha256"],
                "contract_flavor": "testnet-lab" if lab else "production",
                "release_ns": str((FIRST_RELEASE + (art["number"] - 1) * WEEK) * 10**9),
                "source_window": {"start": art["start"], "end": art["end"]}, "wasm": hashes}
    if hashlib.sha256(database.read_bytes()).hexdigest() != before:
        raise RehearsalError("Source database changed during preparation; original was not modified by this command")
    write_json(directory / "prepared.json", manifest)
    values = {"APP_ENV": "development", "EXECUTION_MODE": "testnet_rehearsal", "SERVICE_ROLE": "api",
              "TESTNET_REHEARSAL_DIR": directory.as_posix(), "DATA_DIR": directory.as_posix(),
              "DATABASE_URL": f"sqlite:///{(directory / 'rehearsal.db').as_posix()}",
              "STORAGE_PROVIDER": "local_content_addressed", "NEAR_NETWORK": "testnet", "NEAR_RPC_URL": "https://rpc.testnet.near.org",
              "FIRST_RELEASE_SUNDAY": "2026-11-15", "GENESIS_CHECKPOINT": str(art["start"]),
              "ECONOMY_ENABLED": "true", "ENABLE_CHAIN_WRITES": "false", "MAINNET_WRITES_APPROVED": "false",
              "SCHEDULER_ENABLED": "false", "MARKETPLACE_CROSSCHAIN_ENABLED": "false", "SIGNER_KEY_FILE": "",
              "PROTOCOL_ID": f"intent-distortions-testnet-rehearsal-{name}", "TESTNET_ARTIFACT_BASE_URL": "",
              "PUBLIC_ORIGIN": "http://127.0.0.1:3004", "CORS_ORIGIN": "http://127.0.0.1:3004"}
    values.update({field.upper(): "" for field in ROLES.values()})
    values.update({f"EXPECTED_{role.upper()}_CODE_HASH": digest for role, digest in manifest["wasm"].items()})
    (directory / "profile.env").write_text("# Testnet rehearsal only. Configure public account IDs and the public artifact base URL.\n" +
        "\n".join(f"{key}={json.dumps(value)}" for key, value in values.items()) + "\n", encoding="utf-8")
    return {"status": "prepared", "workspace": str(directory.relative_to(ROOT)), "artwork_id": art["id"],
            "image_sha256": art["image_hash"], "source_unchanged": True, "signed": False}


def local_art(directory):
    config = load_settings(directory)
    manifest = json.loads((Path(directory) / "prepared.json").read_text(encoding="utf-8"))
    factory = init_db(config.database_url, create_schema=False)
    with factory() as db:
        row = db.get(Artwork, manifest["artwork_id"])
        art = copy.deepcopy(row.payload) if row else None
    store = ContentStore(config.data_dir / "content")
    if (not art or art["mode"] not in ("historical_replay", "demo") or art["image_hash"] != manifest["image_sha256"]
            or art["provenance"]["sha256"] != manifest["provenance_sha256"] or art["number"] < 1
            or manifest["release_ns"] != str((FIRST_RELEASE + (art["number"] - 1) * WEEK) * 10**9)
            or not verify_artwork(store, art)["valid"]):
        raise RehearsalError("Prepared historical artwork no longer matches its commitments")
    if publish_traits(store, art)[0]["sha256"] != manifest["trait_sha256"]:
        raise RehearsalError("Prepared frozen traits changed")
    if manifest.get("contract_flavor") != "testnet-lab" and (art["mode"] != "historical_replay" or art["number"] not in (1, 2, 3)):
        raise RehearsalError("Creator-only rehearsal requires the saved historical genesis")
    return config, manifest, factory, store, art


def _account(value, contract=False):
    return bool(ACCOUNT.fullmatch(value) and (value.endswith(".testnet") or not contract and re.fullmatch(r"[a-f0-9]{64}", value)))


def public_base(value):
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment or p.hostname in ("localhost",) or p.hostname.endswith((".local", ".example")):
        raise RehearsalError("Set a public HTTPS artifact base URL without credentials or query strings")
    try:
        if not ipaddress.ip_address(p.hostname).is_global:
            raise RehearsalError("Artifact URLs must be publicly accessible")
    except ValueError as exc:
        if "publicly accessible" in str(exc):
            raise
    return value.rstrip("/")


def requirements(config, assets=True):
    missing = [field.upper() for role, field in ROLES.items() if not _account(getattr(config, field), role in ("nft", "auction", "market"))]
    ids = [getattr(config, field) for field in ROLES.values() if getattr(config, field)]
    if len(set(ids)) != len(ids):
        missing.append("SEPARATE_ROLE_ACCOUNTS")
    if len(config.near_nft_contract) > 40:
        missing.append("NFT_ACCOUNT_MAX_40_BYTES")
    for role in ARTIFACTS:
        if not re.fullmatch(r"[a-f0-9]{64}", getattr(config, f"expected_{role}_code_hash")):
            missing.append(f"EXPECTED_{role.upper()}_CODE_HASH")
    if assets:
        try: public_base(config.testnet_artifact_base_url)
        except ValueError: missing.append("TESTNET_ARTIFACT_BASE_URL")
    return missing


def deployment_plan(directory):
    config, manifest, _, _, _ = local_art(directory)
    missing = requirements(config, assets=False)
    hashes = build_hashes(manifest.get("contract_flavor") == "testnet-lab")
    if any(hashes[role] != getattr(config, f"expected_{role}_code_hash") for role in ARTIFACTS):
        missing.append("REVIEW_CURRENT_WASM_HASHES")
    initializers = {
        "nft": {"owner_id": config.testnet_governance_account, "minter": config.near_minter_account,
                "auction_contract": config.near_auction_contract, "creator": config.near_creator_account, "treasury": config.near_treasury_account},
        "auction": {"owner": config.near_minter_account, "nft_contract": config.near_nft_contract,
                    "creator": config.near_creator_account, "treasury": config.near_treasury_account,
                    "min_bid": str(10**24), "increment": str(10**23)},
        "market": {"nft_contract": config.near_nft_contract, "primary_auction": config.near_auction_contract, "creator": config.near_creator_account}}
    lab = manifest.get("contract_flavor") == "testnet-lab"
    if lab:
        for values in initializers.values(): values["timestamp_ns"] = str(FIRST_RELEASE * 10**9)
        initializers["market"]["clock_authority"] = config.near_minter_account
    operations = [{"role": role, "account": getattr(config, ROLES[role]), "wasm": ARTIFACTS[role], "sha256": hashes[role],
                   "initializer": "new_testnet_lab" if lab else "new" if role == "market" else "new_economy", "args": initializers[role]} for role in ("nft", "auction", "market")]
    value = {"schema": SCHEMA, "network": "testnet", "operations": operations, "vault_sha256": hashes["vault"]}
    return {"status": "blocked" if missing else "ready", "missing": missing, "plan": value, "sha256": sha(canonical(value)).hex(), "signed": False}


def mint_plan(directory):
    config, manifest, _, store, art = local_art(directory)
    missing = requirements(config)
    base = config.testnet_artifact_base_url.rstrip("/") + manifest.get("public_suffix", "")
    traits, ref = publish_traits(store, art)
    ref = {**ref, "uri": base + "/nft-traits.json"}
    metadata = token_metadata(art, traits, ref, base + "/artwork.png", base + "/provenance.json")
    metadata["description"] = ("TESTNET LAB — synthetic fixture. " if art["mode"] == "demo" else "TESTNET REHEARSAL — saved historical artwork. ") + metadata["description"]
    extra = json.loads(metadata["extra"])
    extra["testnet_rehearsal"] = {"source_mode": art["mode"], "source_artwork": art["id"], "source_window": manifest["source_window"]}
    metadata["extra"] = canonical(extra).decode()
    commitment = {"epoch": art["number"], "image_hash": art["image_hash"], "provenance_hash": art["provenance"]["sha256"],
                  "merkle_root": art["merkle_root"], "seed": art["seed"], "block_hash": art["block"]["hash"]}
    value = {"schema": SCHEMA, "network": "testnet", "contract": config.near_nft_contract, "signer": config.near_minter_account,
             "creator": config.near_creator_account, "token_id": art["edition"], "method": "mint_scheduled_artwork", "deposit": "1 NEAR",
             "nft_code_hash": config.expected_nft_code_hash,
             "args": {"release_ns": manifest["release_ns"], "metadata": metadata, "commitment": commitment}}
    return {"status": "blocked" if missing else "ready", "missing": missing, "plan": value, "sha256": sha(canonical(value)).hex(), "signed": False}


async def verify_public_files(directory, client=None):
    config, manifest, _, store, art = local_art(directory)
    base = public_base(config.testnet_artifact_base_url) + manifest.get("public_suffix", "")
    files = json.loads((Path(directory) / ("public" + manifest.get("public_suffix", "")) / "publish-manifest.json").read_text(encoding="utf-8"))["files"]
    provenance = json.loads(store.get(art["provenance"]["sha256"]))
    expected = {"provenance.json": manifest["provenance_sha256"], "nft-traits.json": manifest["trait_sha256"]}
    expected.update({name: provenance["files"][name]["sha256"] for name in ("artwork.png", "artwork.svg", "thumbnail.webp", "artwork-manifest.json") if name in provenance["files"]})
    if files != expected:
        raise RehearsalError("Public-file allowlist differs from the prepared historical artwork")
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as owned:
        for filename, expected in files.items():
            response = await (client or owned).get(base + "/" + filename)
            response.raise_for_status()
            if sha(response.content).hex() != expected:
                raise RehearsalError("Public artifact bytes differ from their frozen commitments")
    return {"files": len(files), "hashes_match": True}


async def verified_contracts(config, rpc):
    await validate_contracts(config, rpc)
    if not config.near_market_contract:
        raise RehearsalError("This rehearsal requires its separately deployed marketplace")
    economy = await rpc.view(config.near_nft_contract, "get_economy", {})
    if economy["vault_code_hash"] != config.expected_vault_code_hash:
        raise RehearsalError("Embedded vault hash differs from the reviewed artifact")


async def check(directory, online=False, rpc=None, client=None):
    config, manifest, _, _, _ = local_art(directory)
    missing = requirements(config)
    result = {"status": "blocked" if missing else "ready_for_online_checks", "missing": missing,
              "source_copy_verified": True, "network": "testnet", "release_ns": manifest["release_ns"],
              "near_cli_installed": bool(shutil.which("near")), "signed": False}
    if online and not missing:
        r = rpc or NearRPC(config.near_rpc_url, budget_seconds=20)
        await verified_contracts(config, r)
        accounts = await asyncio.gather(*(_account_view(r, getattr(config, field)) for field in ROLES.values()))
        operator = accounts[list(ROLES).index("operator")]
        result["minter_funded"] = int(operator["amount"]) >= 101 * 10**22
        result["public_artifacts"] = await verify_public_files(directory, client)
        block = await r.block()
        result["mint_due"] = await contract_time(config, r) >= int(manifest["release_ns"])
        result["status"] = ("ready_to_mint" if result["near_cli_installed"] else "cli_installation_required") if result["mint_due"] else "waiting_for_scheduled_date"
        if not result["minter_funded"]: result["status"] = "minter_funding_required"
    return result


def save_plan(directory, kind):
    directory = workspace(directory)
    result = deployment_plan(directory) if kind == "deploy" else mint_plan(directory)
    write_json(directory / f"{kind}-plan.json", result)
    return {key: value for key, value in result.items() if key != "plan"} | {"plan_file": f"{kind}-plan.json"}


async def _network(rpc):
    if (await rpc.call("status", {}))["chain_id"] != "testnet":
        raise RehearsalError("RPC must report testnet; no signing was attempted")


async def _account_view(rpc, account):
    return await rpc.call("query", {"request_type": "view_account", "account_id": account, "finality": "final"})


async def _deployment_state(rpc, operation):
    state = await _account_view(rpc, operation["account"])
    code = base58.b58decode(state["code_hash"]).hex()
    if code == "00" * 32:
        return "empty"
    if code != operation["sha256"]:
        raise RehearsalError("Contract account contains different code; fresh accounts are required")
    current = await rpc.view(operation["account"], "get_config", {})
    expected = operation["args"]
    if operation["role"] == "nft":
        valid = current.get("version") == "echo-nft-3" and all(current.get(k) == expected[k] for k in ("minter", "auction_contract"))
        economy = await rpc.view(operation["account"], "get_economy", {})
        valid = valid and economy.get("creator") == expected["creator"] and economy.get("treasury") == expected["treasury"]
    elif operation["role"] == "auction":
        valid = current.get("version") == "echo-auction-3" and all(current.get(k) == expected[k] for k in ("owner", "nft_contract", "creator"))
        valid = valid and current.get("treasury_accounts") == [expected["treasury"]] and current.get("splits") == [2000, 8000]
    else:
        valid = current.get("version") == "echo-market-1" and current.get("nft_contract") == expected["nft_contract"] and current.get("primary_auction") == expected["primary_auction"] and current.get("creator") == expected["creator"]
    if operation["initializer"] == "new_testnet_lab":
        authority = expected.get("clock_authority", expected.get("minter", expected.get("owner")))
        valid = valid and current.get("testnet_lab") is True and current.get("clock_initialized") is True and current.get("clock_authority") == authority
    if not valid:
        raise RehearsalError("Existing contract initializer differs; refusing to replace it")
    return "matching"


def _journal(directory):
    path = directory / "operator-journal.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


async def _ack_failure(directory, key, rpc, tx_hash, expected):
    journal = _journal(directory)
    previous = journal.get(key)
    if not previous or not tx_hash:
        return
    if previous.get("expected") != expected:
        raise RehearsalError("Unresolved operation belongs to a different plan; reconcile that original transaction first")
    receipt = await rpc.call("tx", {"tx_hash": tx_hash, "sender_account_id": expected["signer"], "wait_until": "FINAL"})
    if receipt.get("final_execution_status") != "FINAL":
        raise RehearsalError("Wait for the original transaction to reach FINAL before retrying")
    tx = receipt["transaction"]
    actions = tx.get("actions", [])
    calls = [a["FunctionCall"] for a in actions if "FunctionCall" in a]
    if (tx.get("hash") != tx_hash or tx.get("signer_id") != expected["signer"] or tx.get("receiver_id") != expected["contract"]
            or len(calls) != 1 or calls[0]["method_name"] != expected["method"]
            or json.loads(base64.b64decode(calls[0]["args"])) != expected["args"]):
        raise RehearsalError("Failed transaction does not match this exact operation")
    if "code_sha256" in expected:
        codes = [a["DeployContract"]["code"] for a in actions if "DeployContract" in a]
        if len(codes) != 1 or sha(base64.b64decode(codes[0])).hex() != expected["code_sha256"]:
            raise RehearsalError("Failed deployment used different WASM")
    failed = "Failure" in receipt.get("status", {}) or any("Failure" in o["outcome"].get("status", {}) for o in receipt.get("receipts_outcome", []))
    if not failed:
        raise RehearsalError("Transaction has no finalized failure; do not resubmit")
    journal[key] = {**previous, "status": "verified_failed", "failed_transaction": tx_hash}
    write_json(directory / "operator-journal.json", journal)


def _run_cli(directory, key, command, expected, runner=None):
    if not runner and not shutil.which("near"):
        raise RehearsalError("Install official near-cli-rs and configure the testnet OS keychain first")
    journal = _journal(directory)
    previous = journal.get(key)
    if previous and previous["status"] not in ("verified_failed",):
        raise RehearsalError("Previous operation is unresolved; verify onchain state or supply its finalized failed transaction hash")
    # Written before signing. An interrupted process or ambiguous CLI exit must
    # never authorize another transaction automatically.
    journal[key] = {"status": "outcome_unknown", "started_at": int(time.time()), "expected": expected}
    write_json(directory / "operator-journal.json", journal)
    try:
        result = (runner or subprocess.run)(command, check=False, capture_output=True, text=True, timeout=180)
    except Exception:
        raise RehearsalError("CLI outcome is unknown. Reconcile before any retry.") from None
    output = re.sub(r"\x1b\[[0-9;]*m", "", (result.stdout or "") + (result.stderr or ""))
    found = re.search(r"Transaction ID:\s*([1-9A-HJ-NP-Za-km-z]{32,44})", output)
    journal[key].update(cli_exit_code=result.returncode, transaction_hash=found.group(1) if found else None)
    write_json(directory / "operator-journal.json", journal)
    # CLI output is not printed/stored: provider failures can contain credentials.


def _complete(directory, key):
    journal = _journal(directory)
    if key in journal:
        journal[key]["status"] = "verified_onchain"
        write_json(directory / "operator-journal.json", journal)


def _call_command(contract, method, args, signer, deposit="0 NEAR"):
    return ["near", "--quiet", "contract", "call-function", "as-transaction", contract, method, "json-args", canonical(args).decode(),
            "prepaid-gas", "200 Tgas", "attached-deposit", deposit, "sign-as", signer, "network-config", "testnet", "sign-with-keychain", "send"]


def _reviewed(directory, kind, expected_hash):
    path = directory / f"{kind}-plan.json"
    if not path.exists():
        raise RehearsalError("Create and review the plan first")
    saved = json.loads(path.read_text(encoding="utf-8"))
    current = deployment_plan(directory) if kind == "deploy" else mint_plan(directory)
    if current["status"] != "ready" or current["sha256"] != expected_hash or saved != current:
        raise RehearsalError("Plan is incomplete or changed; regenerate and review its SHA-256")
    return current["plan"]


async def deploy(directory, plan_hash, rpc=None, runner=None, failed_tx=None, failed_role=None):
    directory = workspace(directory)
    with operator_lock(directory):
        config = load_settings(directory)
        plan = _reviewed(directory, "deploy", plan_hash)
        r = rpc or NearRPC(config.near_rpc_url, budget_seconds=20)
        await _network(r)
        await asyncio.gather(*(_account_view(r, getattr(config, field)) for field in ROLES.values()))
        # Read every destination before any signed action; a mismatched existing
        # deployment must not allow partial deployment to other accounts.
        for operation in plan["operations"]:
            await _deployment_state(r, operation)
        # Accounts are created/funded separately by the owner. Never overwrite a
        # different deployment or create a key in this process.
        for operation in plan["operations"]:
            key = "deploy:" + operation["role"]
            if await _deployment_state(r, operation) == "matching":
                _complete(directory, key)
                continue
            path = wasm_directory(plan["operations"][0]["initializer"] == "new_testnet_lab") / operation["wasm"]
            expected = {"signer": operation["account"], "contract": operation["account"], "method": operation["initializer"], "args": operation["args"], "code_sha256": operation["sha256"]}
            if failed_tx and failed_role == operation["role"]:
                await _ack_failure(directory, key, r, failed_tx, expected)
            command = ["near", "--quiet", "contract", "deploy", operation["account"], "use-file", str(path), "with-init-call", operation["initializer"],
                       "json-args", canonical(operation["args"]).decode(), "prepaid-gas", "200 Tgas", "attached-deposit", "0 NEAR",
                       "network-config", "testnet", "sign-with-keychain", "send"]
            _run_cli(directory, key, command, expected, runner)
            if await _deployment_state(r, operation) != "matching":
                raise RehearsalError("Deployment is not yet verified. Do not repeat until reconciled.")
            _complete(directory, key)
        await verified_contracts(config, r)
        return {"status": "deployed_and_verified", "network": "testnet", "contracts": [o["account"] for o in plan["operations"]]}


async def _minted(config, plan, rpc):
    token_id = await rpc.view(config.near_nft_contract, "get_epoch_token", {"epoch": plan["args"]["commitment"]["epoch"]})
    if token_id is None:
        return None
    if token_id != plan["token_id"]:
        raise RehearsalError("Onchain epoch conflicts with the prepared artwork")
    token, commitment, wallet = await asyncio.gather(
        rpc.view(config.near_nft_contract, "nft_token", {"token_id": token_id}),
        rpc.view(config.near_nft_contract, "get_provenance", {"token_id": token_id}),
        rpc.view(config.near_nft_contract, "get_edition_wallet", {"token_id": token_id}))
    if not token or commitment != plan["args"]["commitment"] or not wallet or wallet["release_ns"] != plan["args"]["release_ns"]:
        raise RehearsalError("Onchain NFT commitments or scheduled account differ")
    metadata = token.get("metadata", {})
    expected = plan["args"]["metadata"]
    if any(metadata.get(key) != expected[key] for key in ("title", "description", "media", "media_hash", "reference", "reference_hash", "copies")):
        raise RehearsalError("Onchain NFT metadata differs from the reviewed mint")
    extra = json.loads(metadata.get("extra") or "{}")
    wanted = json.loads(expected["extra"])
    if any(extra.get(key) != value for key, value in wanted.items() if key != "attributes") or not all(a in extra.get("attributes", []) for a in wanted["attributes"]):
        raise RehearsalError("Onchain frozen traits or rehearsal label differ")
    return {"token": token, "wallet": wallet}


def _record_mint(directory, plan, result):
    config, _, factory, _, art = local_art(directory)
    with factory.begin() as db:
        row = db.get(Artwork, art["id"])
        row.payload = {**row.payload, "nft": {"status": "minted", "token_id": plan["token_id"], "contract": config.near_nft_contract,
                       "network": "testnet", "evidence": "Finalized testnet contract views; historical provenance preserved"},
                       "auction": {"status": "CreatorMinted" if art["number"] < 4 else "not_created", "token_id": plan["token_id"]}, "wallet": result["wallet"]}


async def mint(directory, plan_hash, rpc=None, client=None, runner=None, failed_tx=None):
    directory = workspace(directory)
    with operator_lock(directory):
        config = load_settings(directory)
        plan = _reviewed(directory, "mint", plan_hash)
        r = rpc or NearRPC(config.near_rpc_url, budget_seconds=20)
        await verified_contracts(config, r)
        await verify_public_files(directory, client)
        result = await _minted(config, plan, r)
        if result is None:
            if await contract_time(config, r) < int(plan["args"]["release_ns"]):
                raise RehearsalError("The scheduled creator edition is not due yet; no mint was submitted")
            if int((await _account_view(r, config.near_minter_account))["amount"]) < 101 * 10**22:
                raise RehearsalError("Fund the minter for the 1 NEAR storage deposit plus gas")
            await _ack_failure(directory, mint_key(directory, plan["token_id"]), r, failed_tx, {"signer": plan["signer"], "contract": plan["contract"], "method": plan["method"], "args": plan["args"]})
            _run_cli(directory, mint_key(directory, plan["token_id"]), _call_command(plan["contract"], plan["method"], plan["args"], plan["signer"], plan["deposit"]),
                     {"signer": plan["signer"], "contract": plan["contract"], "method": plan["method"], "args": plan["args"]}, runner)
            result = await _minted(config, plan, r)
            if result is None:
                raise RehearsalError("Mint outcome is not yet visible. Reconcile; do not submit another transaction.")
        _complete(directory, mint_key(directory, plan["token_id"]))
        _record_mint(directory, plan, result)
        return {"status": "mint_verified", "network": "testnet", "token_id": plan["token_id"],
                "current_owner": result["token"]["owner_id"], "edition_account": result["wallet"]["account_id"],
                "wallet_status": result["wallet"]["wallet_status"], "auction_started": False, "bids_submitted": False}


async def verify_mint(directory, rpc=None):
    directory = workspace(directory)
    with operator_lock(directory):
        return await _verify_mint(directory, rpc)


async def _verify_mint(directory, rpc=None):
    config = load_settings(directory)
    plan = mint_plan(directory)
    if plan["status"] != "ready":
        raise RehearsalError("Configure account IDs and public files before verification")
    r = rpc or NearRPC(config.near_rpc_url, budget_seconds=20)
    await verified_contracts(config, r)
    result = await _minted(config, plan["plan"], r)
    if result is None:
        return {"status": "not_minted", "signed": False}
    _record_mint(directory, plan["plan"], result)
    _complete(Path(directory), mint_key(directory, plan["plan"]["token_id"]))
    return {"status": "mint_verified", "current_owner": result["token"]["owner_id"], "wallet_status": result["wallet"]["wallet_status"], "signed": False}


async def create_wallet(directory, rpc=None, runner=None, failed_tx=None):
    directory = workspace(directory)
    with operator_lock(directory):
        config = load_settings(directory)
        reviewed = json.loads((directory / "mint-plan.json").read_text(encoding="utf-8"))
        plan = _reviewed(directory, "mint", reviewed["sha256"])
        r = rpc or NearRPC(config.near_rpc_url, budget_seconds=20)
        await verified_contracts(config, r)
        result = await _minted(config, plan, r)
        if not result:
            raise RehearsalError("Mint must be verified before creating its dedicated account")
        state = result["wallet"]["wallet_status"]
        if state in ("Uncreated", "Creating"):
            method = "create_edition_wallet" if state == "Uncreated" else "reconcile_wallet"
            args = {"token_id": plan["token_id"]}
            expected = {"signer": config.near_minter_account, "contract": config.near_nft_contract, "method": method, "args": args}
            key = f'wallet:{plan["token_id"]}:{result["wallet"]["creation_attempt"]}:{method}'
            await _ack_failure(directory, key, r, failed_tx, expected)
            _run_cli(directory, key, _call_command(config.near_nft_contract, method, args, config.near_minter_account), expected, runner)
            result = await _minted(config, plan, r)
            if result["wallet"]["wallet_status"] != "Ready":
                raise RehearsalError("Dedicated account is not ready. Inspect funding/resolution before retrying.")
            _complete(directory, key)
        if result["wallet"]["wallet_status"] != "Ready":
            raise RehearsalError("Expected an unfunded creator-edition account")
        account = result["wallet"]["account_id"]
        view, keys, vault = await asyncio.gather(_account_view(r, account),
            r.call("query", {"request_type": "view_access_key_list", "account_id": account, "finality": "final"}),
            r.view(account, "get_state", {}))
        if base58.b58decode(view["code_hash"]).hex() != config.expected_vault_code_hash or keys["keys"] or vault["controller"] != config.near_nft_contract or vault["token_id"] != plan["token_id"]:
            raise RehearsalError("Dedicated account code, controller or keyless policy differs")
        _record_mint(directory, plan, result)
        return {"status": "wallet_verified", "account": account, "keyless": True, "funded_allocation": "0"}


def wasm_directory(lab=False):
    return ROOT / ("contracts/target/testnet-lab/wasm32-unknown-unknown/release" if lab else "contracts/target/wasm32-unknown-unknown/release")


def mint_key(directory, token_id):
    return "mint:" + token_id if testnet_profile.is_lab(load_settings(directory)) else "mint"


async def contract_time(config, rpc):
    if testnet_profile.is_lab(config):
        from .testnet_lab import clock_status
        state = await clock_status(config, rpc, check_lock=False)
        if not state["lab_ready"]: raise RehearsalError("Lab clock/policy could not be verified; check RPC availability and clock synchronization")
        return int(state["lab_clock_ns"])
    return int((await rpc.block())["timestamp_nanosec"])
