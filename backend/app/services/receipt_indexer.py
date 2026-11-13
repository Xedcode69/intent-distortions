from .near_rpc import NearRPC
from .publication import index_receipt

async def ingest(factory,settings,transaction_hash,sender):
    rpc=NearRPC(settings.near_rpc_url)
    result=await rpc.call("tx",{"tx_hash":transaction_hash,"sender_account_id":sender,"wait_until":"FINAL"})
    tx=result.get("transaction",{})
    if result.get("final_execution_status")!="FINAL" or tx.get("hash")!=transaction_hash or tx.get("signer_id")!=sender:
        raise ValueError("Transaction identity/finality mismatch")
    if tx.get("receiver_id")!=settings.near_auction_contract:raise ValueError("Transaction is not addressed to the configured auction")
    if "Failure" in result.get("status",{}):raise ValueError("Failed transaction cannot be indexed as a successful bid")
    await index_receipt(factory,{"transaction_hash":transaction_hash,"receipts_outcome":result.get("receipts_outcome",[])},settings.near_auction_contract,None,rpc)
    return {"verified":True,"transaction_hash":transaction_hash,"source":"finalized NEAR RPC receipts"}
