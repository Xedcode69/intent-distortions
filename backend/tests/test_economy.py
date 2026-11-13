from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from app.config import Settings
from app.services.preflight import validate_contracts
from app.services.economy_keeper import EconomyKeeper

async def test_economy_preflight_checks_bindings_policy_and_embedded_code():
    settings=Settings(_env_file=None,near_nft_contract="nft.testnet",near_auction_contract="auction.testnet",near_minter_account="worker.testnet",
        near_creator_account="team.testnet",near_treasury_account="treasury.testnet",first_release_sunday="2026-11-15",expected_vault_code_hash="ab"*32)
    class RPC:
        bad=False
        async def call(self,method,args):return {"chain_id":"testnet"}
        async def view(self,contract,method,args):
            if method=="get_economy":return {"creator":"team.testnet","treasury":"treasury.testnet","vault_code_hash":("cd" if self.bad else "ab")*32,
                "treasury_bps":2000,"vault_bps":8000,"early_exit_bps_of_vault":4000,"exited_ticket_reentry":False}
            if contract=="nft.testnet":return {"version":"echo-nft-3","minter":"worker.testnet","auction_contract":"auction.testnet"}
            return {"version":"echo-auction-3","owner":"worker.testnet","nft_contract":"nft.testnet","creator":"team.testnet","duration_ns":str(86400*10**9),
                "extension_ns":"0","splits":[2000,8000],"treasury_accounts":["treasury.testnet"]}
    rpc=RPC();assert (await validate_contracts(settings,rpc))["contracts"]=="bindings_and_policy_verified"
    rpc.bad=True
    with pytest.raises(ValueError,match="vault WASM"):await validate_contracts(settings,rpc)

class RPC:
    def __init__(self,*,wallets=None,months=None,auctions=None,now="2026-12-15"):
        self.wallets=wallets or [];self.months=months or [];self.auctions=auctions or []
        self.now=int(datetime.strptime(now,"%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())*10**9
    async def block(self):return {"timestamp_nanosec":str(self.now)}
    async def view(self,contract,method,args):
        if method=="get_config":return {"version":"echo-nft-3"}
        if method=="get_auctions":return self.auctions[args["from_index"]:args["from_index"]+args["limit"]]
        if method=="get_refund_accounts":return []
        if method=="get_edition_wallets":return self.wallets[args["from_index"]:args["from_index"]+args["limit"]]
        if method=="get_months":return self.months[args["from_index"]:args["from_index"]+args["limit"]]
        if method=="get_month":return next((m for m in self.months if m["cycle"]==args["cycle"]),None)
        if method=="get_economy":return {"next_close":202612,"treasury_credit":"0","treasury_pending":None}
        if method=="get_edition_wallet":return next(d for d in self.wallets if d["token_id"]==args["token_id"])
        raise AssertionError(method)

class Writer:
    def __init__(self,rpc):self.rpc=rpc;self.calls=[]
    async def submit(self,key,contract,method,args,deposit="0"):
        self.calls.append((key,contract,method,args,deposit));return {"receipts_outcome":[]}

def keeper(rpc,fetch=None):
    settings=Settings(_env_file=None,enable_chain_writes=True,near_nft_contract="nft.testnet",near_auction_contract="auction.testnet")
    writer=Writer(rpc);return EconomyKeeper(None,settings,writer,fetch),writer

async def test_keeper_recovers_failed_delivery_and_proceeds_without_selecting_recipients():
    rpc=RPC(auctions=[{"token_id":"ECHO-1","status":"RecoveryRequired"},{"token_id":"ECHO-2","status":"FundingFailed"}])
    k,w=keeper(rpc);await k.tick()
    assert [(x[2],x[3],x[4]) for x in w.calls]==[("finalize_auction",{"token_id":"ECHO-1"},"0"),("forward_proceeds",{"token_id":"ECHO-2"},"0")]

async def test_keeper_never_draws_before_all_rollovers_and_wallets_arrive():
    m={"cycle":202612,"status":"Collecting","pending_sources":1,"expected_receipts":3,"received_receipts":2,"entries":[{},{},{}]}
    k,w=keeper(RPC(months=[m]));await k.tick();assert not w.calls

async def test_keeper_uses_contract_fixed_round_and_never_substitutes_another():
    from app.services.randomness import round_for
    cutoff=int(datetime(2027,1,1,tzinfo=timezone.utc).timestamp());rnd=round_for(cutoff+60)
    m={"cycle":202612,"status":"Collecting","pending_sources":0,"expected_receipts":3,"received_receipts":3,"entries":[{},{},{}],"entropy_round":str(rnd),"tokens":[]}
    fetched=[]
    async def fetch(round_number):fetched.append(round_number);return {"signature":"proof","previous_signature":"previous"}
    k,w=keeper(RPC(months=[m],now="2027-01-02"),fetch);await k.tick()
    assert fetched==[rnd]
    draw=next(x for x in w.calls if x[2]=="draw_month")
    assert draw[3]=={"cycle":202612,"signature":"proof","previous_signature":"previous"}
    assert all("winner" not in x[3] and "beneficiary" not in x[3] for x in w.calls)

async def test_keeper_does_not_fetch_randomness_for_zero_or_single_entry():
    async def fetch(_):raise AssertionError("Unnecessary randomness request")
    m={"cycle":202612,"status":"Collecting","pending_sources":0,"expected_receipts":0,"received_receipts":0,"entries":[]}
    k,w=keeper(RPC(months=[m]),fetch);await k.tick()
    assert w.calls[0][2:]==("draw_month",{"cycle":202612,"signature":"","previous_signature":""},"0")

async def test_keeper_does_not_close_a_month_with_unresolved_nft_transfer():
    d={"token_id":"ECHO-1","wallet_status":"Funded","cycle":202612,"exited":False,"collection_cycle":None,"collected":False,"transfer_pending":True}
    m={"cycle":202612,"status":"Open","tokens":["ECHO-1"]}
    k,w=keeper(RPC(wallets=[d],months=[m],now="2027-01-02"));await k.tick();assert not w.calls

async def test_known_failure_does_not_starve_other_work_but_unknown_nonce_stops_keeper():
    from app.services.chain_writer import OutcomeUnknown
    k,w=keeper(RPC())
    async def failed(*args):raise RuntimeError("Finalized chain action failed")
    w.submit=failed
    assert await k.act("nft.testnet","create_edition_wallet",{"token_id":"ECHO-1"},"ECHO-1") is False
    async def unknown(*args):raise OutcomeUnknown("Pending signed transaction")
    w.submit=unknown
    with pytest.raises(OutcomeUnknown):await k.act("nft.testnet","fund_edition_wallet",{"token_id":"ECHO-1"},"ECHO-1")

async def test_readonly_economy_api_has_no_fabricated_accounts_or_prize_balances():
    import httpx
    from app.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
        response=await client.get("/api/v1/economy");assert response.status_code==200
        data=response.json();assert data["status"]=="not_deployed" and data["treasury_earned"]=="0"
        assert (await client.get("/api/v1/economy/wallets")).json()==[]
        assert (await client.get("/api/v1/economy/months")).json()==[]
        assert (await client.get("/api/v1/economy/months/202613")).status_code==422
        assert (await client.get("/api/v1/economy/wallets?limit=10000")).status_code==422
