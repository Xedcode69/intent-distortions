import base64
import copy
import json
import subprocess
from pathlib import Path

import httpx
import pytest

from app.services import testnet_lab, testnet_rehearsal as lab, testnet_profile
from test_testnet_rehearsal import prepared_template, rehearsal, configure, Chain


def full_lab(directory):
    config = configure(directory)
    manifest = json.loads((directory / "prepared.json").read_text(encoding="utf-8"))
    manifest["contract_flavor"] = "testnet-lab"
    lab.write_json(directory / "prepared.json", manifest)
    return config


class LabChain(Chain):
    def __init__(self, directory, config):
        super().__init__(directory, config)
        self.times = {getattr(config, lab.ROLES[role]): lab.FIRST_RELEASE * 10**9 for role in ("nft", "auction", "market")}
        self.tx = {}
    async def view(self, contract, method, args):
        if method == "get_epoch_token":
            return self.token["token_id"] if self.token and self.commitment["epoch"] == args["epoch"] else None
        value = await super().view(contract, method, args)
        if method == "get_config": return {**value, "testnet_lab": True, "clock_initialized": True, "clock_ns": str(self.times[contract]), "clock_authority": self.config.near_minter_account}
        return value
    async def call(self, method, args):
        if method == "tx": return self.tx[args["tx_hash"]]
        return await super().call(method, args)
    def runner(self, command, **kwargs):
        index = command.index("as-transaction")
        contract, method = command[index+1:index+3]
        args = json.loads(command[command.index("json-args")+1])
        if method == "mint_scheduled_artwork":
            result = super().runner(command, **kwargs)
            self.token.update(token_id=f'ECHO-{args["commitment"]["epoch"]:06d}', owner_id=self.config.near_auction_contract)
            return result
        assert "--quiet" not in command  # Official quiet output suppresses transaction IDs.
        self.calls.append(command)
        self.times[contract] = int(args["timestamp_ns"])
        tx_hash = "1" * 31 + str(len(self.calls) + 1)
        self.tx[tx_hash] = {"final_execution_status": "FINAL", "status": {"SuccessValue": ""}, "receipts_outcome": [],
            "transaction": {"signer_id": self.config.near_minter_account, "receiver_id": contract, "actions": [
                {"FunctionCall": {"method_name": method, "args": base64.b64encode(json.dumps(args).encode()).decode(), "deposit": "0"}}]}}
        return subprocess.CompletedProcess(command, 0, stdout="Transaction ID: " + tx_hash, stderr="")


async def test_clock_sync_and_partial_resume(rehearsal):
    directory, _ = rehearsal
    config = full_lab(directory); chain = LabChain(directory, config)
    assert (await testnet_lab.clock_status(config, chain))["lab_ready"]
    chain.times[config.near_nft_contract] += 86400 * 10**9
    assert not (await testnet_lab.clock_status(config, chain))["lab_ready"]
    target = chain.times[config.near_nft_contract]
    assert (await testnet_lab.advance(directory, target, chain, chain.runner))["status"] == "clock_synchronized"
    assert len(chain.calls) == 2  # Already advanced NFT is not submitted twice.
    assert (await testnet_lab.clock_status(config, chain))["lab_ready"]
    await testnet_lab.advance(directory, target, chain, chain.runner)
    assert len(chain.calls) == 2
    with pytest.raises(lab.RehearsalError, match="forward"):
        await testnet_lab.advance(directory, target - 1, chain, chain.runner)
    (directory / "operator.lock").write_text("123")
    assert not (await testnet_lab.clock_status(config, chain))["lab_ready"]


async def test_clock_health_deduplicates_reads_and_rechecks_each_request(rehearsal):
    directory, _ = rehearsal
    config = full_lab(directory)
    class CountingChain(LabChain):
        def __init__(self, *args): super().__init__(*args); self.reads = []
        async def call(self, method, args):
            self.reads.append((method, json.dumps(args, sort_keys=True)))
            return await super().call(method, args)
        async def view(self, account, method, args):
            self.reads.append((account, method))
            return await super().view(account, method, args)
    chain = CountingChain(directory, config)
    assert (await testnet_lab.clock_status(config, chain))["lab_ready"]
    assert len(chain.reads) == len(set(chain.reads)) == 8
    chain.times[config.near_market_contract] += 1
    chain.reads.clear()
    assert not (await testnet_lab.clock_status(config, chain))["lab_ready"]
    assert len(chain.reads) == 8
    (directory / "operator.lock").write_text("123")
    chain.reads.clear()
    assert not (await testnet_lab.clock_status(config, chain))["lab_ready"]
    assert chain.reads == []


async def test_clock_health_timeout_disables_actions(rehearsal, monkeypatch):
    import asyncio
    directory, _ = rehearsal
    config = full_lab(directory)
    class SlowChain(LabChain):
        async def call(self, method, args):
            await asyncio.sleep(1)
            return await super().call(method, args)
    monkeypatch.setattr(testnet_lab, "CLOCK_STATUS_TIMEOUT", .01)
    chain = SlowChain(directory, config)
    state = await testnet_lab.clock_status(config, chain)
    assert not state["lab_ready"] and not chain.calls


@pytest.mark.parametrize("prior,activates", [(None, True), ("CustodyFailed", True), (None, False)])
async def test_keeper_prepares_wallet_before_activation_and_checks_callback(rehearsal, monkeypatch, prior, activates):
    from app.database import Artwork, Epoch
    from app.services.economy_keeper import EconomyKeeper
    directory, _ = rehearsal
    config = full_lab(directory)
    proof = lab.ROOT / "fixtures/sample-epoch/verified-beacon.json"
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_bytes((Path(__file__).resolve().parents[2] / "fixtures/sample-epoch/verified-beacon.json").read_bytes())
    # The keeper consumes publication envelopes, not renderer inputs.
    factory = lab.init_db(config.database_url, create_schema=False)
    with factory.begin() as db:
        db.add(Epoch(id="demo-000004", number=4, mode="demo", status="rendered", start=100, end=200, payload={"records": []}))
        db.flush()
        db.add(Artwork(id="demo-000004", epoch_id="demo-000004", image_hash="fe"*32,
            payload={"id":"demo-000004", "number":4, "edition":"ECHO-000004", "nft":{"status":"minted"}}))
    class CustodyChain(LabChain):
        def __init__(self, *args):
            super().__init__(*args)
            self.ready = False
            self.auction = {"status": prior, "custody_verified": False} if prior else None
        async def view(self, account, method, args):
            if method == "get_auction": return self.auction
            if method == "get_auction_candidate":
                assert self.ready, "Factory must finish before custody is queried"
                return {"token_id":"ECHO-000004", "owner_id":config.near_auction_contract}
            if method == "get_edition_wallet": return {"wallet_status":"Ready" if self.ready else "Uncreated"}
            return await super().view(account, method, args)
    chain = CustodyChain(directory, config)
    async def prepare(self):
        chain.ready = True
    async def submit(directory, config, rpc, contract, method, args, deposit="0", runner=None):
        assert chain.ready
        assert contract == config.near_auction_contract and args == {"token_id":"ECHO-000004"}
        assert method == ("retry_custody" if prior else "create_auction")
        assert deposit == ("0" if prior else str(5*10**22))
        chain.calls.append(method)
        chain.auction = {"status":"Active" if activates else "CustodyFailed", "custody_verified":activates}
        return {"receipts_outcome": []}
    monkeypatch.setattr(EconomyKeeper, "tick", prepare)
    monkeypatch.setattr(testnet_lab, "confirmed_call", submit)
    if not activates:
        with pytest.raises(lab.RehearsalError, match="activation did not verify"):
            await testnet_lab.tick(directory, chain)
    else:
        assert (await testnet_lab.tick(directory, chain))["status"] == "keeper_pass_finalized"
        with factory() as db:
            assert db.get(Artwork,"demo-000004").payload["auction"]["status"] == "Active"
    assert len(chain.calls) == 1


async def test_unknown_action_requires_exact_final_recovery(rehearsal):
    directory, _ = rehearsal
    config = full_lab(directory); chain = LabChain(directory, config)
    def lost_output(command, **kwargs):
        result = chain.runner(command, **kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    target = (lab.FIRST_RELEASE + 86400) * 10**9
    with pytest.raises(lab.RehearsalError, match="transaction ID"):
        await testnet_lab.advance(directory, target, chain, lost_output)
    with pytest.raises(lab.RehearsalError, match="unresolved"):
        await testnet_lab.advance(directory, target, chain, chain.runner)
    tx_hash = next(iter(chain.tx))
    wrong = copy.deepcopy(chain.tx[tx_hash]); wrong["transaction"]["receiver_id"] = "different.testnet"
    chain.tx["wrong"] = wrong
    with pytest.raises(lab.RehearsalError, match="exact pending"):
        await testnet_lab.recover(directory, "wrong", chain)
    assert (await testnet_lab.recover(directory, tx_hash, chain))["success"]
    await testnet_lab.advance(directory, target, chain, chain.runner)
    assert len(chain.calls) == 3


async def test_lab_build_rejected_by_production_preflight(rehearsal):
    from app.services.preflight import validate_contracts
    directory, _ = rehearsal
    config = configure(directory); chain = LabChain(directory, config)
    with pytest.raises(ValueError, match="forbidden"):
        await validate_contracts(config, chain)


def test_lab_deployment_plan_selects_isolated_binaries(rehearsal):
    directory, _ = rehearsal
    config = full_lab(directory)
    for role, name in lab.ARTIFACTS.items():
        destination = lab.wasm_directory(True) / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((lab.wasm_directory(False) / name).read_bytes())
    result = lab.deployment_plan(directory)
    assert result["status"] == "ready"
    assert all(operation["initializer"] == "new_testnet_lab" for operation in result["plan"]["operations"])
    market = result["plan"]["operations"][-1]
    assert market["args"]["clock_authority"] == config.near_minter_account
    assert market["args"]["timestamp_ns"] == str(lab.FIRST_RELEASE * 10**9)


async def test_fixture_editions_are_distinct_and_keep_genesis(rehearsal, monkeypatch):
    directory, _ = rehearsal
    config = full_lab(directory)
    original = lab.local_art(directory)[-1]
    real_root = Path(__file__).resolve().parents[2]
    # The fixture provider is local; no credentials or remote model are used.
    import shutil
    shutil.copytree(real_root / "fixtures", lab.ROOT / "fixtures", dirs_exist_ok=True)
    result = await testnet_lab.fixtures(directory)
    assert result["editions"] == [original["id"], *[f"demo-{n:06d}" for n in range(4, 9)]]
    assert lab.local_art(directory)[-1]["image_hash"] == original["image_hash"]
    hashes = {original["image_hash"]}
    for number in range(4, 9):
        testnet_lab.select_edition(directory, f"demo-{number:06d}")
        art = lab.local_art(directory)[-1]
        assert art["mode"] == "demo"
        assert art["image_hash"] not in hashes
        hashes.add(art["image_hash"])
        plan = lab.mint_plan(directory)["plan"]
        assert "synthetic fixture" in plan["args"]["metadata"]["description"]
        assert f"/demo-{number:06d}/artwork.png" in plan["args"]["metadata"]["media"]
    testnet_lab.select_edition(directory, original["id"])
    assert lab.local_art(directory)[-1]["image_hash"] == original["image_hash"]
    testnet_lab.select_edition(directory, "demo-000004")
    plan = lab.save_plan(directory, "mint")
    chain = LabChain(directory, config)
    chain.times = {account: (lab.FIRST_RELEASE + 3 * lab.WEEK) * 10**9 for account in chain.times}
    def public(request):
        return httpx.Response(200, content=(directory / "public/demo-000004" / request.url.path.split("/")[-1]).read_bytes())
    async with httpx.AsyncClient(transport=httpx.MockTransport(public)) as client:
        minted = await lab.mint(directory, plan["sha256"], chain, client, chain.runner)
        assert minted["current_owner"] == config.near_auction_contract
        await lab.mint(directory, plan["sha256"], chain, client, chain.runner)
    assert len(chain.calls) == 1
    assert lab.local_art(directory)[-1]["auction"]["status"] == "not_created"
