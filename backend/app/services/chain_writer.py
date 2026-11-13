"""Persist the exact signed transaction before submission. Unknown outcomes never re-sign."""
import asyncio
import json
import os
import time
from pathlib import Path
from sqlalchemy import select
from ..config import ROOT
from ..database import Effect
from .canonical_data import canonical,sha
from .near_rpc import NearRPC

class OutcomeUnknown(RuntimeError):pass

class Signer:
    def __init__(self,settings):self.settings=settings
    async def request(self,payload):
        import shutil
        node=shutil.which("node")
        if not node:raise RuntimeError("Node.js runtime is required by the isolated NEAR signer")
        env={**os.environ,"ENABLE_CHAIN_WRITES":str(self.settings.enable_chain_writes).lower(),
             "MAINNET_WRITES_APPROVED":str(self.settings.mainnet_writes_approved).lower(),
             "NEAR_NETWORK":self.settings.near_network,"NEAR_NFT_CONTRACT":self.settings.near_nft_contract,
             "NEAR_AUCTION_CONTRACT":self.settings.near_auction_contract,"NEAR_MARKET_CONTRACT":self.settings.near_market_contract}
        process=await asyncio.create_subprocess_exec(node,str(ROOT/"signer/sign.mjs"),stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env)
        try:out,error=await asyncio.wait_for(process.communicate(canonical({**payload,"key_file":self.settings.signer_key_file,"account_id":self.settings.near_minter_account})),30)
        except TimeoutError:
            process.kill();await process.wait();raise RuntimeError("Signer timed out") from None
        if process.returncode:raise RuntimeError("Signer rejected request")
        return json.loads(out)

class ChainWriter:
    def __init__(self,factory,settings,rpc=None,signer=None):
        self.factory,self.settings=factory,settings
        self.rpc=rpc or NearRPC(settings.near_rpc_url);self.signer=signer or Signer(settings)

    async def submit(self,key,contract,method,args,deposit="0"):
        if not self.settings.enable_chain_writes:raise RuntimeError("Chain writes disabled; publication awaits operator configuration")
        if self.settings.near_network=="mainnet" and not self.settings.mainnet_writes_approved:raise RuntimeError("Mainnet writes not approved")
        digest=sha(canonical({"contract":contract,"method":method,"args":args,"deposit":deposit})).hex()
        with self.factory() as db:effect=db.get(Effect,key)
        if effect:
            if effect.args_hash!=digest:raise ValueError("Idempotency key reused with different transaction arguments")
            if effect.state=="succeeded":return effect.payload
            if effect.state=="failed":raise RuntimeError("Prior chain action failed; explicit reconciled retry required")
        else:
            with self.factory() as db:
                if db.scalar(select(Effect.key).where(Effect.state.in_(["prepared","submitted","unknown"])).limit(1)):
                    raise OutcomeUnknown("Reconcile the prior signed transaction before reserving a new nonce")
            pending_key=await self.signer.request({"op":"public_key"})
            status=await self.rpc.call("status",{})
            if status["chain_id"]!=self.settings.near_network:raise ValueError("Signer RPC network mismatch")
            access=await self.rpc.call("query",{"request_type":"view_access_key","finality":"final",
                "account_id":self.settings.near_minter_account,"public_key":pending_key["public_key"]})
            signed=await self.signer.request({"op":"sign","receiver_id":contract,"method":method,"args":args,
                "gas":"200000000000000","deposit":deposit,"nonce":str(access["nonce"]+1),"block_hash":access["block_hash"]})
            with self.factory.begin() as db:
                # The worker holds a PostgreSQL advisory lock for this signer for its lifetime.
                effect=Effect(key=key,account=self.settings.near_minter_account,contract=contract,method=method,
                    args_hash=digest,state="prepared",signed_transaction=signed["signed_transaction"],
                    transaction_hash=signed["transaction_hash"],created_at=int(time.time()),payload={})
                db.add(effect)
        with self.factory.begin() as db:
            stored=db.get(Effect,key);stored.state="submitted"
        try:
            result=await self.rpc.call("send_tx",{"signed_tx_base64":effect.signed_transaction,"wait_until":"FINAL"})
        except Exception:
            try:result=await self.rpc.call("tx",{"tx_hash":effect.transaction_hash,"sender_account_id":effect.account,"wait_until":"FINAL"})
            except Exception:
                with self.factory.begin() as db:db.get(Effect,key).state="unknown"
                raise OutcomeUnknown("Transaction outcome unknown; exact signed bytes retained for reconciliation") from None
        if result.get("final_execution_status")!="FINAL":
            raise OutcomeUnknown("Transaction has not reached final execution")
        failed="Failure" in result.get("status",{})
        receipt={"transaction_hash":effect.transaction_hash,"final_execution_status":"FINAL",
            "status":result.get("status"),"receipts_outcome":result.get("receipts_outcome",[])}
        with self.factory.begin() as db:
            stored=db.get(Effect,key);stored.state="failed" if failed else "succeeded";stored.payload=receipt
        if failed:raise RuntimeError("Finalized chain action failed")
        return receipt

    async def reconcile_pending(self):
        with self.factory() as db:
            pending=list(db.scalars(select(Effect).where(Effect.state.in_(["prepared","submitted","unknown"])).order_by(Effect.created_at)))
        for effect in pending:
            try:result=await self.rpc.call("tx",{"tx_hash":effect.transaction_hash,"sender_account_id":effect.account,"wait_until":"FINAL"})
            except Exception:
                try:result=await self.rpc.call("send_tx",{"signed_tx_base64":effect.signed_transaction,"wait_until":"FINAL"})
                except Exception:raise OutcomeUnknown("Pending signed transaction cannot yet be reconciled; no new nonce will be signed") from None
            if result.get("final_execution_status")!="FINAL":raise OutcomeUnknown("Pending receipt not final")
            receipt={"transaction_hash":effect.transaction_hash,"status":result.get("status"),"final_execution_status":"FINAL","receipts_outcome":result.get("receipts_outcome",[])}
            with self.factory.begin() as db:
                row=db.get(Effect,effect.key);row.state="failed" if "Failure" in result.get("status",{}) else "succeeded";row.payload=receipt
