import asyncio
import base64
import copy
import json
import shutil
import subprocess
import uuid
from pathlib import Path

import base58
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Artwork
from app.services import testnet_profile
from app.services import testnet_rehearsal as lab
from app.services.canonical_data import canonical, sha
from app.services.provenance import verify_artwork
from app.services.storage import ContentStore
from test_historical_replay import PLAN, MockMainnet, MockExplorer, mock_beacon, base_settings
from app.services.historical_replay import replay_week


@pytest.fixture(scope="module")
def prepared_template(tmp_path_factory):
    root = tmp_path_factory.mktemp("testnet-rehearsal")
    source = root / "data/replays/source"
    from app.services import asset_networks
    async def mapping(records):
        return asset_networks.build_asset_mapping([{"assetId":"nep141:eth-usdc","blockchain":"eth"}, {"assetId":"nep141:wrap.near","blockchain":"near"}], records, observed_at=1)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(asset_networks, "fetch_asset_mapping", mapping)
        asyncio.run(replay_week(PLAN, base_settings(), source, rpc=MockMainnet(), collector=MockExplorer(), beacon_fetch=mock_beacon))
        for name in lab.ARTIFACTS.values():
            path = root / "contracts/target/wasm32-unknown-unknown/release" / name
            path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(name.encode())
        patch.setattr(lab, "ROOT", root)
        patch.setattr(testnet_profile, "REHEARSAL_ROOT", root / "data/testnet-rehearsals")
        before = sha((source / "replay.db").read_bytes()).hex()
        result = lab.prepare(source / "report.json", "template")
        assert result["source_unchanged"] and sha((source / "replay.db").read_bytes()).hex() == before
    return root, source


@pytest.fixture
def rehearsal(prepared_template, monkeypatch):
    root, source = prepared_template
    monkeypatch.setattr(lab, "ROOT", root)
    monkeypatch.setattr(testnet_profile, "REHEARSAL_ROOT", root / "data/testnet-rehearsals")
    template = root / "data/testnet-rehearsals/template"
    directory = template.parent / ("case-" + uuid.uuid4().hex[:12])
    shutil.copytree(template, directory)
    profile = directory / "profile.env"
    profile.write_text(profile.read_text(encoding="utf-8").replace(template.as_posix(), directory.as_posix()), encoding="utf-8")
    return directory, source


def configure(directory):
    path = directory / "profile.env"
    text = path.read_text(encoding="utf-8")
    for role, field in lab.ROLES.items():
        text = text.replace(f'{field.upper()}=""', f'{field.upper()}="{role}.lab.testnet"')
    text = text.replace('TESTNET_ARTIFACT_BASE_URL=""', 'TESTNET_ARTIFACT_BASE_URL="https://art.example.org/demo"')
    path.write_text(text, encoding="utf-8")
    lab.save_plan(directory, "deploy");lab.save_plan(directory, "mint")
    return lab.load_settings(directory)


class Chain:
    def __init__(self, directory, config):
        self.directory=directory;self.config=config;self.network="testnet";self.token=None;self.commitment=None;self.wallet=None
        self.now=(lab.FIRST_RELEASE+1)*10**9;self.calls=[];self.fail=False;self.codes={}
        self.vault_keys=[];self.bad_metadata=False
        for role in ("nft","auction","market"):
            self.codes[getattr(config, lab.ROLES[role])] = getattr(config, f"expected_{role}_code_hash")
    async def call(self, method, args):
        if self.fail: raise RuntimeError("https://provider.example/private-auth-secret")
        if method=="status":return {"chain_id":self.network}
        if method=="query":
            if args["request_type"]=="view_access_key_list":return {"keys":self.vault_keys}
            account=args["account_id"]
            code=self.codes.get(account, self.config.expected_vault_code_hash if account.startswith("november") else "00"*32)
            return {"code_hash":base58.b58encode(bytes.fromhex(code)).decode(),"amount":str(100*10**24),"storage_usage":1000}
        raise AssertionError(method)
    async def block(self):return {"timestamp_nanosec":str(self.now)}
    async def view(self, contract, method, args):
        c=self.config
        if method=="get_config":
            if contract==c.near_nft_contract:return {"version":"echo-nft-3","auction_contract":c.near_auction_contract,"minter":c.near_minter_account,"trait_schema":"echo-nft-traits-v1","market_transfer_schema":"echo-market-transfer-v1","royalty_ownership_schema":"monthly-finalized-owner-v1"}
            if contract==c.near_auction_contract:return {"version":"echo-auction-3","owner":c.near_minter_account,"nft_contract":c.near_nft_contract,"creator":c.near_creator_account,"duration_ns":str(86400*10**9),"extension_ns":"0","splits":[2000,8000],"treasury_accounts":[c.near_treasury_account]}
            return {"version":"echo-market-1","nft_contract":c.near_nft_contract,"primary_auction":c.near_auction_contract,"creator":c.near_creator_account,"fee_bps":500,"royalty_policy":"equal-per-nft-utc-cutoff-v1","currency":"NEAR"}
        if method=="get_economy":return {"creator":c.near_creator_account,"treasury":c.near_treasury_account,"vault_code_hash":c.expected_vault_code_hash,"treasury_bps":2000,"vault_bps":8000,"early_exit_bps_of_vault":4000,"exited_ticket_reentry":False}
        if method=="get_epoch_token":return "ECHO-000001" if self.token else None
        if method=="nft_token":return self.token
        if method=="get_provenance":return self.commitment
        if method=="get_edition_wallet":return self.wallet
        if method=="get_state":return {"controller":c.near_nft_contract,"token_id":"ECHO-000001"}
        raise AssertionError(method)
    def runner(self, command, **kwargs):
        self.calls.append(command)
        assert command[-4:]==["network-config","testnet","sign-with-keychain","send"]
        if "deploy" in command:
            op=json.loads((self.directory / "deploy-plan.json").read_text(encoding="utf-8"))["plan"]["operations"][len(self.calls)-1]
            self.codes[op["account"]]=op["sha256"]
        else:
            method=command[command.index("as-transaction")+2]
            args=json.loads(command[command.index("json-args")+1])
            assert method in ("mint_scheduled_artwork","create_edition_wallet","reconcile_wallet")
            if method=="mint_scheduled_artwork":
                self.token={"token_id":"ECHO-000001","owner_id":self.config.near_creator_account,"metadata":copy.deepcopy(args["metadata"])}
                self.commitment=args["commitment"]
                self.wallet={"release_ns":args["release_ns"],"account_id":"november2026-edition-1."+self.config.near_nft_contract,"wallet_status":"Uncreated","creation_attempt":0,"cycle":None}
            else:self.wallet.update(wallet_status="Ready",creation_attempt=1)
        return subprocess.CompletedProcess(command,0,stdout="",stderr="")


def public_client(directory, tamper=False):
    def handle(request):
        path=directory / "public" / request.url.path.split("/")[-1]
        return httpx.Response(200,content=b"changed" if tamper else path.read_bytes())
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))

async def test_edition_wallet_journal_does_not_collide_with_an_earlier_edition(rehearsal):
    directory,_=rehearsal;config=configure(directory);chain=Chain(directory,config)
    plan=lab.save_plan(directory,"mint")
    async with public_client(directory) as client:await lab.mint(directory,plan["sha256"],chain,client,chain.runner)
    journal=lab._journal(directory)
    # Previous versions used this same key for every edition's first attempt.
    journal["wallet:0:create_edition_wallet"]={"status":"verified_onchain","expected":{"args":{"token_id":"ECHO-000000"}}}
    lab.write_json(directory/"operator-journal.json",journal)
    assert (await lab.create_wallet(directory,chain,chain.runner))["status"]=="wallet_verified"
    assert lab._journal(directory)["wallet:ECHO-000001:0:create_edition_wallet"]["status"]=="verified_onchain"


def test_preparation_copies_originals_and_exports_no_records(rehearsal):
    directory, source=rehearsal
    config, manifest, _, store, art=lab.local_art(directory)
    assert config.execution_mode=="testnet_rehearsal" and art["mode"]=="historical_replay"
    assert verify_artwork(store,art,True)["valid"]
    assert manifest["source_database_sha256"]==sha((source/"replay.db").read_bytes()).hex()
    assert {p.name for p in (directory/"public").iterdir()}=={"artwork.png","artwork.svg","artwork-manifest.json","thumbnail.webp","provenance.json","nft-traits.json","publish-manifest.json"}
    assert not (directory/"public/source-snapshot.json").exists()
    with pytest.raises(ValueError,match="exists"):lab.prepare(source/"report.json","template")


async def test_readiness_lists_missing_details_without_network_or_signing(rehearsal):
    directory,_=rehearsal
    report=await lab.check(directory)
    assert report["status"]=="blocked" and "NEAR_CREATOR_ACCOUNT" in report["missing"]
    assert "TESTNET_ARTIFACT_BASE_URL" in report["missing"] and not report["signed"]
    assert not (directory/"operator-journal.json").exists()


@pytest.mark.parametrize("field,value",[("NEAR_NETWORK","mainnet"),("SCHEDULER_ENABLED","true"),("ENABLE_CHAIN_WRITES","true"),("MARKETPLACE_CROSSCHAIN_ENABLED","true"),("APP_ENV","production")])
def test_profile_rejects_mainnet_and_background_operations(rehearsal,field,value):
    directory,_=rehearsal;path=directory/"profile.env"
    lines=[f'{field}="{value}"' if line.startswith(field+"=") else line for line in path.read_text(encoding="utf-8").splitlines()]
    path.write_text("\n".join(lines)+"\n")
    with pytest.raises(ValueError):lab.load_settings(directory)


def test_profile_ignores_ambient_credentials_and_rejects_source_database(rehearsal,monkeypatch):
    directory,source=rehearsal
    monkeypatch.setenv("NEAR_NETWORK","mainnet");monkeypatch.setenv("SIGNER_KEY_FILE","private.json");monkeypatch.setenv("NEAR_AI_API_KEY","should-not-load")
    config=lab.load_settings(directory)
    assert config.near_network=="testnet" and not config.signer_key_file and not config.near_ai_api_key
    p=directory/"profile.env";p.write_text(p.read_text(encoding="utf-8").replace((directory/"rehearsal.db").as_posix(),(source/"replay.db").as_posix()))
    with pytest.raises(ValueError):lab.load_settings(directory)


async def test_mint_is_idempotent_preserves_provenance_and_never_bids(rehearsal):
    directory,source=rehearsal;config=configure(directory);chain=Chain(directory,config)
    before=sha((source/"replay.db").read_bytes()).hex()
    plan=lab.mint_plan(directory)
    async with public_client(directory) as client:
        first=await lab.mint(directory,plan["sha256"],rpc=chain,client=client,runner=chain.runner)
        again=await lab.mint(directory,plan["sha256"],rpc=chain,client=client,runner=chain.runner)
    assert first==again and len(chain.calls)==1
    assert first["current_owner"]==config.near_creator_account and not first["auction_started"] and not first["bids_submitted"]
    _,_,_,store,art=lab.local_art(directory)
    assert art["mode"]=="historical_replay" and art["nft"]["status"]=="minted" and verify_artwork(store,art,True)["valid"]
    assert sha((source/"replay.db").read_bytes()).hex()==before
    chain.token["owner_id"]="collector.testnet"
    assert (await lab.verify_mint(directory,rpc=chain))["current_owner"]=="collector.testnet"
    assert len(chain.calls)==1


@pytest.mark.parametrize("problem",["wrong_plan","not_due","wrong_network","changed_asset","wrong_wasm"])
async def test_mint_checks_fail_before_signing(rehearsal,problem):
    directory,_=rehearsal;config=configure(directory);chain=Chain(directory,config);digest=lab.mint_plan(directory)["sha256"]
    if problem=="wrong_plan":digest="00"*32
    elif problem=="not_due":chain.now=1
    elif problem=="wrong_network":chain.network="mainnet"
    elif problem=="wrong_wasm":chain.codes[config.near_nft_contract]="cd"*32
    async with public_client(directory,tamper=problem=="changed_asset") as client:
        with pytest.raises(ValueError):await lab.mint(directory,digest,rpc=chain,client=client,runner=chain.runner)
    assert not chain.calls


async def test_unknown_outcome_is_not_automatically_resubmitted(rehearsal):
    directory,_=rehearsal;config=configure(directory);chain=Chain(directory,config);plan=lab.mint_plan(directory)
    calls=[]
    def unknown(command,**kwargs):calls.append(command);return subprocess.CompletedProcess(command,1,stdout="",stderr="private provider error")
    async with public_client(directory) as client:
        with pytest.raises(ValueError,match="not yet visible"):await lab.mint(directory,plan["sha256"],rpc=chain,client=client,runner=unknown)
        with pytest.raises(ValueError,match="unresolved"):await lab.mint(directory,plan["sha256"],rpc=chain,client=client,runner=unknown)
    assert len(calls)==1
    assert "private provider" not in (directory/"operator-journal.json").read_text(encoding="utf-8")
    chain.runner(calls[0])
    assert (await lab.verify_mint(directory,rpc=chain))["status"]=="mint_verified"
    assert json.loads((directory/"operator-journal.json").read_text(encoding="utf-8"))["mint"]["status"]=="verified_onchain"


async def test_wallet_creation_is_separate_and_checks_keys(rehearsal):
    directory,_=rehearsal;config=configure(directory);chain=Chain(directory,config);plan=lab.mint_plan(directory)
    async with public_client(directory) as client:
        await lab.mint(directory,plan["sha256"],rpc=chain,client=client,runner=chain.runner)
    result=await lab.create_wallet(directory,rpc=chain,runner=chain.runner)
    assert result["keyless"] and len(chain.calls)==2
    await lab.create_wallet(directory,rpc=chain,runner=chain.runner)
    assert len(chain.calls)==2
    chain.vault_keys=[{"public_key":"unexpected"}]
    with pytest.raises(ValueError,match="keyless"):await lab.create_wallet(directory,rpc=chain,runner=chain.runner)


async def test_deployment_skips_matching_contracts_and_refuses_different_code(rehearsal):
    directory,_=rehearsal;config=configure(directory);chain=Chain(directory,config);plan=lab.deployment_plan(directory)
    assert (await lab.deploy(directory,plan["sha256"],rpc=chain,runner=chain.runner))["status"]=="deployed_and_verified"
    assert not chain.calls
    chain.codes[config.near_nft_contract]="ff"*32
    with pytest.raises(ValueError,match="different code"):await lab.deploy(directory,plan["sha256"],rpc=chain,runner=chain.runner)
    assert not chain.calls


async def test_empty_contracts_are_deployed_once_with_atomic_initializers(rehearsal):
    directory,_=rehearsal;config=configure(directory);chain=Chain(directory,config);plan=lab.deployment_plan(directory)
    chain.codes={account:"00"*32 for account in chain.codes}
    result=await lab.deploy(directory,plan["sha256"],rpc=chain,runner=chain.runner)
    assert result["status"]=="deployed_and_verified" and len(chain.calls)==3
    assert all("with-init-call" in command for command in chain.calls)
    await lab.deploy(directory,plan["sha256"],rpc=chain,runner=chain.runner)
    assert len(chain.calls)==3


async def test_only_the_exact_failed_transaction_clears_an_unknown_attempt(rehearsal):
    directory,_=rehearsal;config=configure(directory);chain=Chain(directory,config);plan=lab.mint_plan(directory)
    expected={"signer":plan["plan"]["signer"],"contract":plan["plan"]["contract"],"method":plan["plan"]["method"],"args":plan["plan"]["args"]}
    lab.write_json(directory/"operator-journal.json",{"mint":{"status":"outcome_unknown","expected":expected}})
    tx_hash="1"*44;original=chain.call
    async def tx_call(method,args):
        if method!="tx":return await original(method,args)
        return {"transaction":{"hash":tx_hash,"signer_id":expected["signer"],"receiver_id":expected["contract"],
                "actions":[{"FunctionCall":{"method_name":expected["method"],"args":base64.b64encode(canonical(expected["args"])).decode()}}]},"status":{"Failure":{"ActionError":{}}},"final_execution_status":"FINAL"}
    chain.call=tx_call
    with pytest.raises(ValueError,match="different plan"):
        await lab._ack_failure(directory,"mint",chain,tx_hash,{**expected,"contract":"another.testnet"})
    async with public_client(directory) as client:
        result=await lab.mint(directory,plan["sha256"],rpc=chain,client=client,runner=chain.runner,failed_tx=tx_hash)
    assert result["status"]=="mint_verified" and len(chain.calls)==1


def test_server_environment_excludes_credentials_and_signing(rehearsal,monkeypatch):
    directory,_=rehearsal
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]/"scripts"))
    from serve_testnet import server_environments
    monkeypatch.setenv("NEAR_AI_API_KEY","ambient-private-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY","ambient-aws-secret")
    monkeypatch.setenv("SIGNER_KEY_FILE","operator-private.json")
    api,web=server_environments(directory,8002,3004)
    assert api['EXECUTION_MODE']=='testnet_rehearsal' and api['NEAR_NETWORK']=='testnet'
    assert api['ENABLE_CHAIN_WRITES']=='false' and not api['SIGNER_KEY_FILE']
    assert web['ECHOES_NEXT_DIST_DIR']=='.next-testnet'
    assert not any(key.startswith(('NEAR_','AWS_','S3_','SIGNER_')) for key in web)
    assert 'DATABASE_URL' not in web and 'ECHOES_ENV_FILE' not in web
    assert 'ambient-private-secret' not in json.dumps(api)+json.dumps(web)
def test_api_serves_historical_proofs_in_distinct_testnet_mode(rehearsal,monkeypatch):
    directory,_=rehearsal
    import app.main as api
    config=lab.load_settings(directory)
    engine=create_engine(config.database_url,connect_args={"check_same_thread":False})
    monkeypatch.setattr(api,"factory",sessionmaker(engine,expire_on_commit=False))
    monkeypatch.setattr(api,"settings",config);monkeypatch.setattr(api,"store",ContentStore(directory/"content"))
    with TestClient(api.app) as client:
        health=client.get('/api/v1/health').json()
        assert health['mode']=='testnet_rehearsal' and health['network']=='testnet'
        art=client.get('/api/v1/artworks/latest').json()
        assert art['mode']=='historical_replay'
        assert client.get('/api/v1/artworks/'+art['id']+'/verify').json()['valid']
        assert client.get('/api/v1/drops').json()['previous'][0]['id']==art['id']
        assert client.post('/api/v1/demo/run-epoch').status_code==404
        assert client.get('/api/v1/replay/progress').status_code==404
    engine.dispose()
