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
