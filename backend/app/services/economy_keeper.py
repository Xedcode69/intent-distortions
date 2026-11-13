"""Deterministic, permission-limited keeper; no LLM decides destinations or winners."""
import logging
import httpx
from .randomness import CHAIN_HASH, verify_beacon, GENESIS_TIME, PERIOD
from .publication import index_receipt
from .chain_writer import OutcomeUnknown

log=logging.getLogger("echoes.economy")

class EconomyKeeper:
    def __init__(self,factory,settings,writer,beacon_fetch=None):
        self.factory,self.settings,self.writer=factory,settings,writer
        self.rpc=writer.rpc
        self.beacon_fetch=beacon_fetch or self.fetch_beacon
        self.bucket=0

    async def fetch_beacon(self,round_number):
        async with httpx.AsyncClient(timeout=30) as client:
            response=await client.get(f"https://api.drand.sh/{CHAIN_HASH}/public/{round_number}")
            response.raise_for_status()
            return verify_beacon(response.json(),round_number)

    async def act(self,contract,method,args,label):
        try:
            receipt=await self.writer.submit(f"economy:{method}:{label}:{self.bucket}",contract,method,args)
        except OutcomeUnknown:
            raise  # Never reserve another nonce until this exact transaction is reconciled.
        except RuntimeError as exc:
            # A known failed account-creation/retry must not starve an unrelated
            # month's prize or another bidder's refund. No provider text is logged.
            log.error("economy_action_failed method=%s label=%s error_type=%s",method,label,type(exc).__name__)
            return False
        await index_receipt(self.factory,receipt,contract,args.get("token_id",""),self.rpc)
        return True

    async def pages(self,contract,method):
        offset=0
        while True:
            rows=await self.rpc.view(contract,method,{"from_index":offset,"limit":100})
            for row in rows:yield row
            if len(rows)<100:break
            offset+=len(rows)

    async def tick(self):
        if not self.settings.enable_chain_writes:return
        nft,auction=self.settings.near_nft_contract,self.settings.near_auction_contract
        config=await self.rpc.view(nft,"get_config",{})
        if config.get("version")!="echo-nft-3":raise ValueError("Economy keeper requires economy contracts")
        block=await self.rpc.block();now_ns=int(block["timestamp_nanosec"]);self.bucket=now_ns//(300*10**9)
        async for a in self.pages(auction,"get_auctions"):
            token=a["token_id"];args={"token_id":token}
            method=None
            if a["status"]=="Active" and now_ns>=int(a["end_ns"]):method="finalize_auction"
            elif a["status"]=="RecoveryRequired":method="finalize_auction"
            elif a["status"]=="SettlementPending":method="reconcile_settlement"
            elif a["status"]=="FundingFailed":method="forward_proceeds"
            elif a["status"]=="FundingPending":method="reconcile_funding"
            if method:await self.act(auction,method,args,token)
        async for refund in self.pages(auction,"get_refund_accounts"):
            if int(refund["amount"])>0:await self.act(auction,"process_refund",{"account":refund["account"]},refund["account"])
        async for d in self.pages(nft,"get_edition_wallets"):
            token=d["token_id"];args={"token_id":token};method=None
            if d["wallet_status"]=="Uncreated":method="create_edition_wallet"
            elif d["wallet_status"] in ("Creating","Funding"):method="reconcile_wallet"
            elif d["wallet_status"]=="Ready" and d["cycle"] is not None:method="fund_edition_wallet"
            if method:await self.act(nft,method,args,token)
            if d["exited"]:await self.act(nft,"dispatch_exit",args,token)
            if d["collection_cycle"] is not None and not d["collected"]:await self.act(nft,"collect_edition",args,token)
        economy=await self.rpc.view(nft,"get_economy",{})
        if int(economy["treasury_credit"])>0 and economy["treasury_pending"] is None:
            await self.act(nft,"process_treasury",{},"treasury")
        # Draw prior closed months before attempting the next close. Contract state
        # enforces sequential closure and complete incoming rollover independently.
        months=[]
        async for month in self.pages(nft,"get_months"):months.append(month)
        months.sort(key=lambda m:m["cycle"])
        for m in months:
            cycle=m["cycle"]
            if m["status"]=="Collecting" and m["pending_sources"]==0 and m["expected_receipts"]==m["received_receipts"]:
                proof={"signature":"","previous_signature":""}
                if len(m["entries"])>1:
                    rnd=int(m["entropy_round"])
                    if now_ns//10**9<GENESIS_TIME+(rnd-1)*PERIOD:continue
                    try:
                        beacon=await self.beacon_fetch(rnd)
                    except (httpx.HTTPError,ValueError):
                        log.warning("fixed_monthly_beacon_unavailable cycle=%s round=%s",cycle,rnd)
                        continue
                    proof={key:beacon[key] for key in proof}
                await self.act(nft,"draw_month",{"cycle":cycle,**proof},str(cycle))
            elif m["status"]=="Drawn" and m.get("payout",{}).get("status")=="Retryable":
                await self.act(nft,"pay_month",{"cycle":cycle},str(cycle))
        from datetime import datetime,timezone
        cycle=economy["next_close"];year,month=divmod(cycle,100)
        cutoff=int(datetime(year+(month==12),1 if month==12 else month+1,1,tzinfo=timezone.utc).timestamp())*10**9
        if now_ns>=cutoff:
            previous_cycle=(year-1)*100+12 if month==1 else cycle-1
            previous=next((m for m in months if m["cycle"]==previous_cycle),None)
            if cycle==202612 or previous and previous["status"] in ("Drawn","Carried") and previous["pending_sources"]==0:
                # Wait for all vault funding and transfer resolutions, rather than
                # consuming a known-failing transaction on every poll.
                target=await self.rpc.view(nft,"get_month",{"cycle":cycle})
                ready=True
                for token in (target or {}).get("tokens",[]):
                    d=await self.rpc.view(nft,"get_edition_wallet",{"token_id":token})
                    ready=ready and d["wallet_status"]=="Funded" and not d["transfer_pending"]
                if ready:await self.act(nft,"close_month",{"cycle":cycle},str(cycle))
