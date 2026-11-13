import json
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.database import Base,ChainEvent
from app.services.publication import index_receipt

async def test_only_successful_configured_receipts_are_indexed_idempotently(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'receipts.db'}");Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    log="EVENT_JSON:"+json.dumps({"standard":"near_echoes","version":"1.0.0","event":"bid","data":[{"token_id":"ECHO-000001","bidder":"alice.testnet","amount":"100"}]})
    def outcome(id,executor,status):return {"id":id,"block_hash":"block-1","outcome":{"executor_id":executor,"status":status,"logs":[log]}}
    receipt={"transaction_hash":"transaction-1","receipts_outcome":[outcome("valid","auction.testnet",{"SuccessValue":""}),outcome("reverted","auction.testnet",{"Failure":{}}),outcome("wrong-contract","attacker.testnet",{"SuccessValue":""})]}
    class RPC:
        async def call(self,method,args):assert method=="block";return {"header":{"height":100,"timestamp_nanosec":"100000000000"}}
    await index_receipt(factory,receipt,"auction.testnet",None,RPC())
    await index_receipt(factory,receipt,"auction.testnet",None,RPC())
    with factory() as db:rows=list(db.scalars(select(ChainEvent)))
    assert len(rows)==1 and rows[0].receipt_id=="valid" and rows[0].payload["amount"]=="100"
    engine.dispose()

async def test_market_receipts_are_finality_checked_and_executor_bound(monkeypatch,tmp_path):
    from app.services import receipt_indexer
    from app.config import Settings
    import pytest
    engine=create_engine(f"sqlite:///{tmp_path/'market-receipts.db'}");Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    event="EVENT_JSON:"+json.dumps({'standard':'near_echoes_market','event':'sold','data':[{'token_id':'ECHO-000001','amount':'1000'}]})
    class RPC:
        bad=False
        def __init__(self,*_):pass
        async def call(self,method,args):
            if method=='block':return {'header':{'height':10,'timestamp_nanosec':'1000'}}
            return {'final_execution_status':'FINAL','transaction':{'hash':'tx','signer_id':'buyer.testnet','receiver_id':'attacker.testnet' if self.bad else 'market.testnet'},'status':{'SuccessValue':''},
                'receipts_outcome':[{'id':'market-sale','block_hash':'b','outcome':{'executor_id':'market.testnet','status':{'SuccessValue':''},'logs':[event]}}]}
    monkeypatch.setattr(receipt_indexer,'NearRPC',RPC)
    s=Settings(_env_file=None,near_market_contract='market.testnet',near_nft_contract='nft.testnet')
    assert (await receipt_indexer.ingest(factory,s,'tx','buyer.testnet'))['verified']
    with factory() as db:assert db.scalar(select(ChainEvent)).kind=='sold'
    RPC.bad=True
    with pytest.raises(ValueError,match='configured'):await receipt_indexer.ingest(factory,s,'tx','buyer.testnet')
    engine.dispose()
