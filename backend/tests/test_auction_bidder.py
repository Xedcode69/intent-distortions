import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.config import Settings
from app.services import auction_bidder


class RPC:
    def __init__(self, registered=False, refund="0"):
        self.registered,self.refund,self.calls=registered,refund,[]
    async def view(self,contract,method,args):
        self.calls.append((contract,method,args))
        return self.registered if method=="is_bidder_registered" else self.refund


@pytest.mark.parametrize("registered", [False,True])
async def test_bidder_status_uses_current_account_and_reports_refund(registered):
    settings=Settings(_env_file=None,near_auction_contract="auction.testnet")
    rpc=RPC(registered,"42")
    state=await auction_bidder.bidder_status(settings,"bidder.testnet",rpc)
    assert state=={"account_id":"bidder.testnet","contract":"auction.testnet","registered":registered,"refund_yocto":"42"}
    assert len(rpc.calls)==2 and all(call[2]=={"account":"bidder.testnet"} for call in rpc.calls)


@pytest.mark.parametrize("registered,refund", [(None,"0"),("true","0"),(False,"-1"),(True,str(2**128))])
async def test_invalid_provider_state_never_becomes_unregistered(registered,refund):
    with pytest.raises(RuntimeError,match="Invalid bidder"):
        await auction_bidder.bidder_status(Settings(_env_file=None,near_auction_contract="auction.testnet"),"bidder.testnet",RPC(registered,refund))


async def test_invalid_account_is_rejected_before_rpc():
    rpc=RPC()
    with pytest.raises(ValueError):
        await auction_bidder.bidder_status(Settings(_env_file=None,near_auction_contract="auction.testnet"),"bad/account",rpc)
    assert not rpc.calls


def test_bidder_route_is_read_only_and_does_not_require_artwork(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,"settings",Settings(_env_file=None,app_env="test",near_auction_contract="auction.testnet"))
    rpc=RPC()
    monkeypatch.setattr(auction_bidder,"NearRPC",lambda *args,**kwargs:rpc)
    app=FastAPI();app.add_api_route("/api/v1/auctions/bidders/{account_id}",main.auction_bidder,methods=["GET"])
    with TestClient(app) as client:
        response=client.get("/api/v1/auctions/bidders/bidder.testnet")
        assert response.status_code==200 and response.json()["registered"] is False
        assert client.post("/api/v1/auctions/bidders/bidder.testnet").status_code==405
    assert len(rpc.calls)==2
