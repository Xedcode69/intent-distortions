import base64,json
from types import SimpleNamespace
import base58
import pytest
from app.services.reward_cycles import summarize_cycles,reward_snapshot,cutoff_ns

NOW=int(cutoff_ns(202612))+86400*10**9
def wallet(token,cycle,original=1000,**changes):
    return {"token_id":token,"cycle":cycle,"original":str(original),"remaining":str(original),"wallet_status":"Funded","exited":False,"collected":False,"transfer_pending":False,**changes}
def month(cycle,**changes):
    return {"cycle":cycle,"status":"Open","pot":"0","rollover_received":"0","entries":[],"prize":"0","winner":None,"payout":None,"cutoff_ns":cutoff_ns(cycle),**changes}
def by_cycle(rows):return {row["cycle"]:row for row in rows}

def test_open_month_counts_funded_tickets_and_projects_rollover_without_a_new_ticket():
    wallets=[wallet("eligible",202701,800),wallet("exit",202701,1000,exited=True,remaining="600"),wallet("previous-exit",202612,1000,exited=True,remaining="600"),wallet("creator",None,0),wallet("pending",202701,300,wallet_status="Funding")]
    rows=summarize_cycles(wallets,[month(202701,pot="100",rollover_received="100")],NOW);m=by_cycle(rows)[202701]
    assert rows[0]["cycle"]==202701
    assert m["eligible_nfts"]==1 and m["draw_amount"]=="1500" and m["early_withdrawals"]==1
    assert m["incoming_rollover"]=="700" and m["incoming_pending"]=="600" and m["next_month_rollover"]=="600"
    assert m["pending_funding"]==1 and m["pending_funding_amount"]=="300"
    feb=by_cycle(rows)[202702];assert feb["status"]=="Upcoming" and not feb["recorded"] and feb["draw_amount"]=="600" and feb["eligible_nfts"]==0

def test_collection_and_rollover_receipts_never_double_count_funds():
    wallets=[wallet("eligible",202701,800,collected=True,remaining="0"),wallet("previous-exit",202612,1000,exited=True,collected=True,remaining="0")]
    m=by_cycle(summarize_cycles(wallets,[month(202701,status="Collecting",pot="1400",rollover_received="600",entries=[{"token_id":"eligible","beneficiary":"old-owner"}])],NOW))[202701]
    assert m["draw_amount"]=="1400" and m["eligible_nfts"]==1 and m["awaiting_collection"]=="0" and m["incoming_pending"]=="0"

def test_final_draw_uses_frozen_ticket_count_and_prize_not_the_empty_paid_pot():
    m=by_cycle(summarize_cycles([wallet("nft",202612,1000,collected=True,remaining="0")],[month(202612,status="Drawn",prize="1000",entries=[{}],payout={"status":"Paid","amount":"1000"})],NOW))[202612]
    assert m["eligible_nfts"]==1 and m["draw_amount"]=="1000"

def test_historical_exit_rollover_survives_collection_and_empty_draw_carry_is_disjoint():
    wallets=[wallet("exited",202701,1001,exited=True,collected=True,remaining="0")]
    rows=by_cycle(summarize_cycles(wallets,[month(202701,status="Carried",rollover_received="500"),month(202702,pot="1101",rollover_received="1101")],NOW))
    assert rows[202701]["next_month_rollover"]=="1101" and rows[202701]["early_exit_amount"]=="400"
    assert rows[202701]["draw_amount"]=="0" and rows[202702]["draw_amount"]=="1101"
    assert rows[202702]["incoming_pending"]=="0" and rows[202702]["eligible_nfts"]==0

def test_latest_withdrawal_changes_count_pool_and_rollover_without_storing_artwork_rows():
    live=wallet("nft",202701,1300)
    first=by_cycle(summarize_cycles([live],[month(202701)],NOW))[202701]
    changed=by_cycle(summarize_cycles([{**live,"exited":True,"remaining":"780"}],[month(202701)],NOW))[202701]
    assert first["eligible_nfts"]==1 and first["draw_amount"]=="1300"
    assert changed["eligible_nfts"]==0 and changed["draw_amount"]=="0" and changed["early_withdrawals"]==1 and changed["next_month_rollover"]=="780"
    assert "token_id" not in changed

async def test_snapshot_checks_network_code_and_one_finalized_block(monkeypatch):
    from app.config import Settings
    settings=Settings(_env_file=None,near_nft_contract="nft.testnet",expected_nft_code_hash="ab"*32)
    class RPC:
        bad=False
        async def block(self):return {"height":100,"hash":"one-finalized-block","timestamp_nanosec":str(NOW)}
        async def call(self,method,args):
            if method=="status":return {"chain_id":"testnet"}
            assert args["block_id"]=="one-finalized-block"
            if args["request_type"]=="view_account":return {"code_hash":base58.b58encode(bytes.fromhex(("cd" if self.bad else "ab")*32)).decode()}
            value={"get_config":{"version":"echo-nft-3"},"get_edition_wallets":[wallet("nft",202701)],"get_months":[month(202701)]}[args["method_name"]]
            return {"result":list(json.dumps(value).encode())}
    rpc=RPC();result=await reward_snapshot(settings,rpc)
    assert result["block_height"]==100 and result["months"][0]["draw_amount"]=="1000"
    rpc.bad=True
    with pytest.raises(ValueError,match="identity"):await reward_snapshot(settings,rpc)

def test_preview_has_no_fake_monthly_balances_and_limits_are_enforced(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.config import Settings
    import app.rewards_api as m
    monkeypatch.setattr(m,"settings",Settings(_env_file=None));app=FastAPI();app.include_router(m.router)
    with TestClient(app) as client:
        assert client.get('/api/v1/economy/cycles').json()["months"]==[]
        assert client.get('/api/v1/economy/cycles?limit=1000').status_code==422

def test_manual_refresh_rechecks_chain_snapshot_instead_of_reusing_the_view_cache(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.config import Settings
    import app.rewards_api as m
    calls=[]
    async def snapshot(*_):
        calls.append(1);return {"status":"onchain","network":"testnet","months":[{"cycle":202701,"eligible_nfts":len(calls)}]}
    monkeypatch.setattr(m,"settings",Settings(_env_file=None,near_nft_contract="nft.testnet",expected_nft_code_hash="ab"*32));monkeypatch.setattr(m,"reward_snapshot",snapshot);monkeypatch.setattr(m,"_cache",{})
    app=FastAPI();app.include_router(m.router)
    with TestClient(app) as client:
        assert client.get('/api/v1/economy/cycles').json()["months"][0]["eligible_nfts"]==1
        assert client.get('/api/v1/economy/cycles').json()["months"][0]["eligible_nfts"]==1
        assert client.get('/api/v1/economy/cycles?fresh=true').json()["months"][0]["eligible_nfts"]==2
