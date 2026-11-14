import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.database import Base,Artwork,Release,Observation
from app.services.randomness import select_timestamp
from app.services.preflight import validate_contracts
from app.workers.production import Worker
from test_dataset import raw

async def test_worker_observes_before_freeze_reuses_inputs_and_waits_for_signer(tmp_path,monkeypatch):
    from app.services import asset_networks
    async def registry(records):
        return asset_networks.build_asset_mapping([
            {"assetId":"nep141:eth-usdc","blockchain":"eth"},
            {"assetId":"nep141:wrap.near","blockchain":"near"}],records,observed_at=1)
    monkeypatch.setattr(asset_networks,"fetch_asset_mapping",registry)
    beacon=json.loads((Path(__file__).resolve().parents[2]/"fixtures/sample-epoch/verified-beacon.json").read_text())
    sunday=beacon["released_at"]-18*3600;now=[beacon["released_at"]+30]
    settings=Settings(_env_file=None,app_env="test",execution_mode="live",data_dir=tmp_path,near_intents_partner_jwt="unit-test",first_release_sunday="2026-11-08",genesis_checkpoint=1793491200,genesis_checkpoint_ns="1793491200000000000",near_ai_api_key="",near_nft_contract="",near_auction_contract="")
    engine=create_engine(f"sqlite:///{tmp_path/'worker.db'}");Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    class RPC:
        def __init__(self):self.lookups=0
        async def first_block_at(self,target):
            self.lookups+=1
            return {"height":42,"hash":"11111111111111111111111111111111","timestamp_ns":str(target*10**9+200000000),"verified":True}
        async def verify_selected_block(self,block,target):assert int(block["timestamp_ns"])==target*10**9+200000000;return True
    class Collector:
        async def collect(self,start,end,page_size,on_page,statuses):
            assert statuses==("SUCCESS",)
            rows=[raw(i,start+100+i) for i in range(5)];on_page(rows)
            return rows,{"complete":True,"pages":1,"query":{"start":start,"end":end}}
    async def fetch(timestamp):assert timestamp==beacon["released_at"];return beacon
    rpc=RPC();worker=Worker(factory,settings,clock=lambda:now[0],collector=Collector(),rpc=rpc,beacon_fetch=fetch)
    await worker.advance(1);now[0]+=30;await worker.advance(1)
    with factory() as db:
        release=db.get(Release,1);assert release.state=="collecting"
        assert len(list(db.scalars(select(Observation))))==2
        assert db.get(Artwork,"live-000001") is None
    now[0]=release.freeze_at+1;await worker.advance(1)
    with factory() as db:
        art=db.get(Artwork,"live-000001").payload
        assert art["stats"]["total_swaps"]==5 and art["nft"]["status"]=="not_minted"
        assert db.get(Release,1).state=="rendered"
    await worker.advance(1)
    with factory() as db:
        assert db.get(Release,1).state=="awaiting_signer"
        assert db.get(Artwork,"live-000001").image_hash==art["image_hash"]
    assert rpc.lookups==1
    engine.dispose()

async def test_online_contract_preflight_rejects_compressed_auction_and_wrong_binding():
    settings=Settings(_env_file=None,economy_enabled=False,near_minter_account="worker.testnet",near_nft_contract="nft.testnet",near_auction_contract="auction.testnet")
    class RPC:
        duration=604800*10**9
        async def call(self,method,args):return {"chain_id":"testnet"}
        async def view(self,contract,method,args):
            if contract=="nft.testnet":return {"version":"echo-nft-2","minter":"worker.testnet","auction_contract":"auction.testnet"}
            return {"version":"echo-auction-2","owner":"worker.testnet","nft_contract":"nft.testnet","duration_ns":str(self.duration),"extension_ns":str(300*10**9),"splits":[6000,2500,1500],"treasury_accounts":["creative.testnet","dev.testnet","community.testnet"]}
    rpc=RPC();assert (await validate_contracts(settings,rpc))["contracts"]=="bindings_and_policy_verified"
    rpc.duration=60*10**9
    with pytest.raises(ValueError,match="duration"):await validate_contracts(settings,rpc)
