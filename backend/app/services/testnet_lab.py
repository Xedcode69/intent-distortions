"""Explicit CLI-only rehearsal controls. The HTTP service never loads signing keys."""
import asyncio
import base64
import json
from pathlib import Path

from . import testnet_rehearsal as lab
from .testnet_profile import is_lab, validate_clock_build
from .near_rpc import NearRPC
from .canonical_data import canonical, sha

CLOCK_STATUS_TIMEOUT = 12


class _ReadSnapshot:
    """One request's deduplicated public RPC reads, never reused across requests."""
    def __init__(self, rpc):
        self.rpc, self.pending = rpc, {}

    async def _read(self, kind, *args):
        key = (kind, json.dumps(args, sort_keys=True))
        if key not in self.pending:
            self.pending[key] = asyncio.create_task(getattr(self.rpc, kind)(*args))
        return await self.pending[key]

    async def call(self, method, args):
        return await self._read("call", method, args)

    async def view(self, account, method, args):
        return await self._read("view", account, method, args)


async def _verified_clock_configs(config, rpc):
    snapshot = _ReadSnapshot(rpc)
    accounts = (config.near_nft_contract, config.near_auction_contract, config.near_market_contract)
    # Fetch independent policy, code and clock reads together. The existing
    # preflight then validates those exact responses without duplicate requests.
    await asyncio.gather(snapshot.call("status", {}),
        *(snapshot.view(account, "get_config", {}) for account in accounts),
        *(lab._account_view(snapshot, account) for account in accounts),
        snapshot.view(config.near_nft_contract, "get_economy", {}))
    await lab._network(snapshot)
    await lab.verified_contracts(config, snapshot)
    return await asyncio.gather(*(snapshot.view(account, "get_config", {}) for account in accounts))


async def clock_status(config, rpc=None, check_lock=True):
    result = {"lab_ready": False, "lab_clock_ns": None, "lab_entropy": "historical verified drand round 6624326"}
    if not is_lab(config):
        return {"lab_ready": True}  # Original creator-only rehearsal uses the chain clock.
    if not all((config.near_nft_contract, config.near_auction_contract, config.near_market_contract)):
        return result
    if check_lock and (config.testnet_rehearsal_dir / "operator.lock").exists():
        return result
    rpc = rpc or NearRPC(config.near_rpc_url, budget_seconds=8)
    try:
        configs = await asyncio.wait_for(_verified_clock_configs(config, rpc), CLOCK_STATUS_TIMEOUT)
        for value in configs: validate_clock_build(config, value)
        times = {int(value["clock_ns"]) for value in configs}
        result["lab_clock_ns"] = str(max(times))
        result["lab_ready"] = len(times) == 1 and not (check_lock and (config.testnet_rehearsal_dir / "operator.lock").exists())
    except Exception:
        pass  # Public health never returns provider errors/URLs.
    return result


def require_lab(directory):
    config = lab.load_settings(directory)
    if not is_lab(config): raise lab.RehearsalError("Prepare a separate --full-lab workspace first")
    if lab.requirements(config, assets=False): raise lab.RehearsalError("Configure the public testnet account IDs first")
    return config


async def finalized(rpc, tx_hash, expected):
    receipt = await rpc.call("tx", {"tx_hash": tx_hash, "sender_account_id": expected["signer"], "wait_until": "FINAL"})
    receipt["transaction_hash"] = tx_hash
    transaction = receipt.get("transaction", {})
    if receipt.get("final_execution_status") != "FINAL": raise lab.RehearsalError("Wait for FINAL execution before continuing")
    actions = transaction.get("actions", [])
    calls = [a["FunctionCall"] for a in actions if "FunctionCall" in a]
    if (transaction.get("signer_id") != expected["signer"] or transaction.get("receiver_id") != expected["contract"]
        or len(actions) != 1 or len(calls) != 1 or calls[0].get("method_name") != expected["method"]
        or json.loads(base64.b64decode(calls[0]["args"])) != expected["args"]
        or str(calls[0].get("deposit")) != str(expected["deposit_yocto"])):
        raise lab.RehearsalError("Recovery transaction does not match the exact pending lab action")
    success = "SuccessValue" in receipt.get("status", {})
    # Include all descendant execution failures, not just the initiating receipt.
    failed = any("Failure" in row.get("outcome", {}).get("status", {}) for row in receipt.get("receipts_outcome", []))
    return receipt, success and not failed


async def recover(directory, tx_hash, rpc=None):
    config = require_lab(directory)
    with lab.operator_lock(directory):
        rpc = rpc or NearRPC(config.near_rpc_url)
        await lab._network(rpc)
        journal = lab._journal(directory)
        pending = [(key, value) for key, value in journal.items() if key.startswith("lab:") and value["status"] == "outcome_unknown"]
        if len(pending) != 1: raise lab.RehearsalError("Recovery requires exactly one unresolved lab action")
        key, value = pending[0]
        _, success = await finalized(rpc, tx_hash, value["expected"])
        journal[key].update(status="verified_onchain" if success else "verified_failed", transaction_hash=tx_hash)
        lab.write_json(Path(directory) / "operator-journal.json", journal)
        return {"status": "reconciled", "success": success, "transaction_hash": tx_hash}


async def confirmed_call(directory, config, rpc, contract, method, args, deposit="0", runner=None):
    journal = lab._journal(directory)
    if any(value["status"] == "outcome_unknown" for value in journal.values()):
        raise lab.RehearsalError("Reconcile the unresolved operator action before signing another one")
    key = f"lab:{len(journal):06d}:{method}"
    expected = {"signer": config.near_minter_account, "contract": contract, "method": method, "args": args, "deposit_yocto": deposit}
    command = lab._call_command(contract, method, args, config.near_minter_account, deposit + " yoctoNEAR")
    # near-cli-rs quiet mode returns only the contract result, suppressing the ID
    # needed for independent FINAL receipt verification. Output is captured/redacted.
    command.remove("--quiet")
    lab._run_cli(directory, key, command, expected, runner)
    record = lab._journal(directory)[key]
    if not record.get("transaction_hash"):
        raise lab.RehearsalError("CLI did not expose a transaction ID. Use recover with the exact transaction hash before continuing")
    receipt, success = await finalized(rpc, record["transaction_hash"], expected)
    journal = lab._journal(directory)
    journal[key]["status"] = "verified_onchain" if success else "verified_failed"
    lab.write_json(Path(directory) / "operator-journal.json", journal)
    if not success: raise lab.RehearsalError("Lab action finalized with a failure. Inspect its public receipts before proceeding")
    return receipt


async def advance(directory, timestamp_ns, rpc=None, runner=None):
    directory = lab.workspace(directory)
    config = require_lab(directory)
    with lab.operator_lock(directory):
        rpc = rpc or NearRPC(config.near_rpc_url)
        await lab.verified_contracts(config, rpc)
        accounts = (config.near_nft_contract, config.near_auction_contract, config.near_market_contract)
        states = await asyncio.gather(*(rpc.view(account, "get_config", {}) for account in accounts))
        if not 1794700800000000000 <= timestamp_ns <= 2114380800000000000 or any(int(s["clock_ns"]) > timestamp_ns for s in states):
            raise lab.RehearsalError("The lab clock can only move forward within the supported dates")
        for account, state in zip(accounts, states):
            if int(state["clock_ns"]) < timestamp_ns:
                await confirmed_call(directory, config, rpc, account, "lab_set_time", {"timestamp_ns": str(timestamp_ns)}, runner=runner)
        final = await asyncio.gather(*(rpc.view(account, "get_config", {}) for account in accounts))
        if any(int(state["clock_ns"]) != timestamp_ns for state in final): raise lab.RehearsalError("Clocks differ; finish synchronization before using the site")
        return {"status": "clock_synchronized", "timestamp_ns": str(timestamp_ns), "network": "testnet"}


async def fixtures(directory):
    """Deterministic additional editions; never relabel synthetic records as historical."""
    from ..config import Settings
    from .epoch_manager import run_epoch
    directory = lab.workspace(directory)
    config = lab.load_settings(directory)
    if not is_lab(config): raise lab.RehearsalError("Synthetic auction fixtures require --full-lab")
    with lab.operator_lock(directory):
        fixture = json.loads((lab.ROOT / "fixtures/sample-epoch/transactions.json").read_text(encoding="utf-8"))
        evidence = json.loads((lab.ROOT / "fixtures/sample-epoch/evidence.json").read_text(encoding="utf-8"))
        settings = Settings(_env_file=None, execution_mode="demo", data_dir=directory, database_url=config.database_url,
                            near_ai_api_key="", near_intents_partner_jwt="", storage_provider="local_content_addressed")
        factory = lab.init_db(config.database_url, create_schema=False)
        manifest = json.loads((directory / "prepared.json").read_text(encoding="utf-8"))
        manifest.setdefault("editions", {manifest["artwork_id"]: {k: v for k, v in manifest.items() if k not in ("editions", "wasm")}})
        for number in (4, 5, 6, 7, 8):
            art = await run_epoch(factory, settings, number=number, mode="demo", raw=fixture["records"], start=fixture["start"], end=fixture["end"],
                block=evidence["block"], beacon=evidence["beacon"], selection=evidence["selection"], source=fixture["source"])
            store = lab.ContentStore(directory / "content")
            if not lab.verify_artwork(store, art, True)["valid"]: raise lab.RehearsalError("Synthetic fixture verification failed")
            traits, ref = lab.publish_traits(store, art)
            suffix = "/" + art["id"]
            public = directory / ("public" + suffix); public.mkdir(exist_ok=True)
            provenance = json.loads(store.get(art["provenance"]["sha256"]))
            lab._safe_public_document(provenance)
            files = {"provenance.json": art["provenance"]["sha256"], "nft-traits.json": ref["sha256"]}
            files.update({name: provenance["files"][name]["sha256"] for name in ("artwork.png", "artwork.svg", "thumbnail.webp", "artwork-manifest.json")})
            for filename, digest in files.items(): (public / filename).write_bytes(store.get(digest))
            lab.write_json(public / "publish-manifest.json", {"schema": lab.SCHEMA, "files": files, "notice": "Synthetic testnet fixture; not historical weekly activity"})
            manifest["editions"][art["id"]] = {"artwork_id": art["id"], "artifact_mode": "demo", "source_mode": "historical_replay", "image_sha256": art["image_hash"],
                "provenance_sha256": art["provenance"]["sha256"], "trait_sha256": traits["sha256"], "source_window": {"start": art["start"], "end": art["end"]},
                "release_ns": str((lab.FIRST_RELEASE + (number - 1) * lab.WEEK) * 10**9), "public_suffix": suffix}
        lab.write_json(directory / "prepared.json", manifest)
        return {"status": "fixtures_verified", "editions": list(manifest["editions"]), "signed": False}


def select_edition(directory, artwork_id):
    directory = lab.workspace(directory)
    with lab.operator_lock(directory):
        manifest = json.loads((directory / "prepared.json").read_text(encoding="utf-8"))
        if artwork_id not in manifest.get("editions", {}): raise lab.RehearsalError("Choose an edition listed by fixtures")
        # A pending mint cannot be forgotten by changing the active selection.
        if any(row["status"] == "outcome_unknown" for row in lab._journal(directory).values()): raise lab.RehearsalError("Reconcile pending actions before selecting another edition")
        manifest.pop("public_suffix", None)
        manifest.update(manifest["editions"][artwork_id])
        lab.write_json(directory / "prepared.json", manifest)
        lab.local_art(directory)
        return {"status": "selected", "artwork_id": artwork_id, "signed": False}


async def tick(directory, rpc=None, runner=None):
    """One explicit keeper pass: settlement, vaults, refunds, prizes and royalties."""
    from .economy_keeper import EconomyKeeper
    from .publication import index_receipt
    directory = lab.workspace(directory)
    config = require_lab(directory)
    rpc = rpc or NearRPC(config.near_rpc_url)
    await lab.verified_contracts(config, rpc)
    state = await clock_status(config, rpc)
    if not state["lab_ready"]: raise lab.RehearsalError("Synchronize the lab clock first")
    timestamp = state["lab_clock_ns"]
    class ClockRPC:
        async def block(self): return {"timestamp_nanosec": timestamp}
        def __getattr__(self, name): return getattr(rpc, name)
    class Writer:
        pass
    writer = Writer(); writer.rpc = ClockRPC()
    factory = lab.init_db(config.database_url, create_schema=False)
    proof = json.loads((lab.ROOT / "fixtures/sample-epoch/verified-beacon.json").read_text(encoding="utf-8"))
    async def beacon(round_number):
        if round_number != proof["round"]: raise lab.RehearsalError("Unexpected lab entropy round")
        from .randomness import verify_beacon
        return verify_beacon(proof, round_number)
    class Keeper(EconomyKeeper):
        async def act(self, contract, method, args, label, deposit="0"):
            receipt = await confirmed_call(directory, config, rpc, contract, method, args, deposit, runner)
            await index_receipt(factory, receipt, contract, args.get("token_id", ""), rpc)
            return True
    with lab.operator_lock(directory):
        # An economy auction is eligible only after its dedicated account is
        # Ready. Finalize factory receipts before requesting auction custody.
        with factory() as db: arts = list(db.scalars(lab.select(lab.Artwork)))
        await Keeper(factory, config.model_copy(update={"enable_chain_writes": True}), writer, beacon_fetch=beacon).tick()
        for row in arts:
            art = row.payload
            if art["nft"]["status"] != "minted" or art["number"] < 4: continue
            token = art["edition"]
            auction = await rpc.view(config.near_auction_contract, "get_auction", {"token_id": token})
            if auction is None or auction["status"] in ("CheckingCustody", "CustodyFailed"):
                candidate = await rpc.view(config.near_nft_contract, "get_auction_candidate", {"token_id": token})
                if not candidate or candidate["owner_id"] != config.near_auction_contract or candidate["token_id"] != token:
                    raise lab.RehearsalError("Edition account and auction custody are not ready; inspect factory state before retrying")
                method = "create_auction" if auction is None else "retry_custody"
                deposit = str(5 * 10**22) if auction is None else "0"
                receipt = await confirmed_call(directory, config, rpc, config.near_auction_contract, method, {"token_id": token}, deposit, runner)
                await index_receipt(factory, receipt, config.near_auction_contract, token, rpc)
                auction = await rpc.view(config.near_auction_contract, "get_auction", {"token_id": token})
                if not auction or auction["status"] != "Active" or not auction["custody_verified"]:
                    raise lab.RehearsalError("Auction activation did not verify custody; bidding remains disabled")
        # Sync only mutable chain envelopes; art, inputs and proof hashes stay frozen.
        for row in arts:
            art = row.payload
            if art["nft"]["status"] != "minted": continue
            token = art["edition"]
            wallet = await rpc.view(config.near_nft_contract, "get_edition_wallet", {"token_id": token})
            auction = await rpc.view(config.near_auction_contract, "get_auction", {"token_id": token}) if art["number"] >= 4 else {"status": "CreatorMinted", "token_id": token}
            with factory.begin() as db:
                current = db.get(lab.Artwork, art["id"])
                current.payload = {**current.payload, "wallet": wallet, "auction": auction or {"status": "not_created"}}
    return {"status": "keeper_pass_finalized", "clock_ns": timestamp, "repeat": "Run tick again to advance dependent receipt stages"}
