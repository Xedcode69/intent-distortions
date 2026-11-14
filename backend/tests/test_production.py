from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.database import Base,Effect,Observation,Swap
from app.services.chain_writer import ChainWriter,OutcomeUnknown
from app.services.ingestion import persist_page
from app.services.protocol import ensure_protocol
from app.workers.production import choose_observation
from app.services.merkle import proof_index,proof_from_levels,verify
from app.services.canonical_data import snapshot,canonical,sha
from app.services.art_renderer import scene
from app.services.art_statistics import statistics
from app.services.near_ai import fallback
from app.services.art_seed import GENESIS_HASH
from test_dataset import raw

@pytest.fixture
def factory(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'operations.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(engine,expire_on_commit=False)
    engine.dispose()

def test_production_configuration_fails_closed_and_hides_secrets():
    secret="credential-value-must-never-appear"
    with pytest.raises(ValueError) as error:
        Settings(_env_file=None,app_env="production",admin_token=secret,near_ai_api_key=secret)
    assert secret not in str(error.value)
    assert "PostgreSQL" in str(error.value) and "disable AI fallback" in str(error.value)
    assert secret not in repr(Settings(_env_file=None,near_ai_api_key=secret))

def test_frozen_policy_cannot_be_changed(factory):
    settings=Settings(_env_file=None)
    first,_=ensure_protocol(factory,settings)
    assert ensure_protocol(factory,settings)[0]==first
    settings.reconciliation_delay_seconds+=1
    with pytest.raises(ValueError,match="configuration changed"):ensure_protocol(factory,settings)

def observation(i,completed,digest="aa"):
    return Observation(id=i,completed_at=completed,snapshot_hash=digest)

def test_freeze_uses_latest_two_consistent_complete_observations():
    rows=[observation(1,95),observation(2,99),observation(3,101,"late")]
    assert choose_observation(rows,100,10).id==2
    with pytest.raises(ValueError,match="disagree"):
        choose_observation([*rows,observation(4,100,"different")],100,10)
    with pytest.raises(ValueError,match="No two"):
        choose_observation([observation(1,89),observation(2,99)],100,10)

def test_ingestion_reconciles_status_without_storing_deposit_identity(factory):
    first=raw(1,100,status="PROCESSING")
    persist_page(factory,[first]);persist_page(factory,[{**first,"status":"SUCCESS"}])
    with factory() as db:rows=list(db.scalars(select(Swap)))
    assert len(rows)==1 and rows[0].status=="SUCCESS"
    assert "depositAddress" not in rows[0].normalized
    assert first["depositAddress"] not in canonical(rows[0].normalized).decode()

class FakeSigner:
    def __init__(self):self.signs=0
    async def request(self,request):
        if request["op"]=="public_key":return {"public_key":"ed25519:test"}
        self.signs+=1
        return {"signed_transaction":"exact-signed-bytes","transaction_hash":"hash-1"}

class FakeRPC:
    def __init__(self):self.available=False;self.broadcasts=[]
    async def call(self,method,params):
        if method=="status":return {"chain_id":"testnet"}
        if method=="query":return {"nonce":10,"block_hash":"block"}
        if method=="send_tx":self.broadcasts.append(params["signed_tx_base64"])
        if method in ("send_tx","tx"):
            if not self.available:raise TimeoutError("network interruption")
            return {"final_execution_status":"FINAL","status":{"SuccessValue":""},"receipts_outcome":[]}
        raise AssertionError(method)

async def test_ambiguous_chain_submission_never_resigns_or_reuses_nonce(factory):
    settings=Settings(_env_file=None,enable_chain_writes=True,near_minter_account="worker.testnet")
    rpc=FakeRPC();signer=FakeSigner();writer=ChainWriter(factory,settings,rpc,signer)
    with pytest.raises(OutcomeUnknown):await writer.submit("mint-1","nft.testnet","mint_weekly_artwork",{"epoch":1})
    with factory() as db:
        effect=db.get(Effect,"mint-1")
        assert effect.state=="unknown" and effect.signed_transaction=="exact-signed-bytes"
    with pytest.raises(OutcomeUnknown):await writer.submit("list-1","auction.testnet","create_auction",{})
    with pytest.raises(ValueError,match="different"):await writer.submit("mint-1","nft.testnet","mint_weekly_artwork",{"epoch":2})
    assert signer.signs==1
    rpc.available=True
    await writer.reconcile_pending()
    result=await writer.submit("mint-1","nft.testnet","mint_weekly_artwork",{"epoch":1})
    assert result["transaction_hash"]=="hash-1" and signer.signs==1
    assert rpc.broadcasts==["exact-signed-bytes"]

def test_compact_merkle_index_recovers_membership_for_odd_leaf_count():
    records=snapshot([raw(i,100+i) for i in range(101)],100,300)
    index=proof_index(records);tree=[[bytes.fromhex(h) for h in row] for row in index["levels"]]
    assert sum(map(len,tree))<2*len(records)+10
    for i in (0,49,100):assert verify(records[i],proof_from_levels(tree,i),index["levels"][-1][0])

@pytest.mark.parametrize("family",["orbital_network","spiral_constellation","flow_field","fractal_branches","crystalline","particle_nebula"])
def test_six_families_are_bounded_deterministic_and_distinct(family):
    records=snapshot([raw(i,100+i) for i in range(10001)],100,20000)
    stats=statistics(records,100,20000);seed="01"*32
    direction={**fallback(seed,stats).model_dump(),"composition":family}
    manifest=scene(seed,records,stats,direction,100,20000,GENESIS_HASH,1)
    assert manifest==scene(seed,records,stats,direction,100,20000,GENESIS_HASH,1)
    assert len(manifest["shapes"])<6000
    assert sum(s["layer"]=="routes" for s in manifest["shapes"])<=len(stats["chains"])**2
    orbital=scene(seed,records,stats,{**direction,"composition":"orbital_network"},100,20000,GENESIS_HASH,1)
    if family!="orbital_network":assert manifest["shapes"]!=orbital["shapes"]

def test_production_router_physically_removes_demo_endpoints():
    from fastapi import FastAPI
    from app.middleware import remove_demo_routes
    app=FastAPI()
    app.add_api_route("/api/v1/demo/status",lambda:{})
    app.add_api_route("/api/v1/health",lambda:{})
    remove_demo_routes(app)
    assert "/api/v1/demo/status" not in app.openapi()["paths"]
    assert "/api/v1/health" in app.openapi()["paths"]

async def test_chunked_body_limit_rejects_before_application():
    from app.middleware import RequestLimits
    called=False;messages=[]
    async def app(*args):
        nonlocal called
        called=True
    chunks=iter([{"type":"http.request","body":b"a"*600,"more_body":True},{"type":"http.request","body":b"b"*600,"more_body":False}])
    async def receive():return next(chunks)
    async def send(message):messages.append(message)
    await RequestLimits(app,max_bytes=1024)({"type":"http","path":"/api/v1/receipts","client":("test",123)},receive,send)
    assert not called and messages[0]["status"]==413
