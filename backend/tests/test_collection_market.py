import base64
import json
from types import SimpleNamespace
import pytest
from app.services.collection_market import collection_snapshot,collection_page

def token(i,owner="owner.near",approval=1):
    return {"token_id":f"ECHO-{i:06d}","owner_id":owner,"approved_account_ids":{"market.near":approval},
        "metadata":{"title":f"Artwork {i}","extra":json.dumps({"attributes":[{"trait_type":"Art family","value":"Crystalline"}]})}}

def listing(i,price="100",**overrides):
    return {"token_id":f"ECHO-{i:06d}","seller":"owner.near","approval_id":1,"price":price,"sale":None,"expires_ns":"200",**overrides}

async def test_collection_snapshot_pins_every_page_to_one_block_and_orders_before_pagination():
    tokens=[token(i) for i in range(1,126)]
    listings=[listing(1),listing(125,"200"),listing(2,seller="old.near"),listing(3,approval_id=2),listing(4,expires_ns="99"),listing(5,sale={"id":"1"})]
    class RPC:
        async def block(self):return {"hash":"fixed-final-block","height":123,"timestamp_nanosec":"100"}
        async def call(self,method,args):
            assert method=="query" and args["block_id"]=="fixed-final-block" and "finality" not in args
            a=json.loads(base64.b64decode(args["args_base64"]))
            if args["method_name"]=="nft_total_supply":return {"result":list(b'"125"')}
            if args["method_name"]=="get_config":return {"result":list(b'{}')}
            rows=tokens if args["method_name"]=="nft_tokens" else listings
            start=int(a.get("from_index",a.get("offset",0)))
            return {"result":list(json.dumps(rows[start:start+a["limit"]]).encode())}
    s=await collection_snapshot(RPC(),SimpleNamespace(near_nft_contract="nft.near",near_market_contract="market.near"))
    assert s["stats"]=={"items":125,"listed":2,"owners":1,"floor":"100","on_auction":0,"sold":0,"unsold":0}
    p=collection_page(s,limit=1,sort="price");assert p["items"][0]["nft"]["token_id"]=="ECHO-000001"
    assert collection_page(s,offset=1,limit=1)["items"][0]["nft"]["token_id"]=="ECHO-000001"
    assert collection_page(s,status="listed")["total"]==2
    assert collection_page(s,status="unlisted")["total"]==123
    assert collection_page(s,owner="other.near")["total"]==0
    assert collection_page(s,search="ARTWORK 125",family="Crystalline")["total"]==1

async def test_lab_uses_virtual_clock_and_never_mislabels_expired_listings():
    class RPC:
        async def block(self):return {"hash":"block","height":2,"timestamp_nanosec":"100"}
        async def call(self,method,args):
            if args["method_name"]=="nft_total_supply":return {"result":list(b'"1"')}
            value={"clock_ns":"300"} if args["method_name"]=="get_config" else [token(1)] if args["method_name"]=="nft_tokens" else [listing(1)]
            return {"result":list(json.dumps(value).encode())}
    s=await collection_snapshot(RPC(),SimpleNamespace(near_nft_contract="nft.near",near_market_contract="market.near"))
    assert s["stats"]["listed"]==0 and s["stats"]["floor"] is None

def test_collection_api_rejects_invalid_filters_and_empty_preview_is_truthful(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.config import Settings
    import app.marketplace_api as m
    monkeypatch.setattr(m,"settings",Settings(_env_file=None));app=FastAPI();app.include_router(m.router)
    with TestClient(app) as c:
        data=c.get("/api/v1/marketplace/collection").json();assert data["total"]==0 and data["stats"]["floor"] is None
        for query in ("status=invalid","sort=random","limit=200","owner=Invalid!","search="+"a"*121):assert c.get("/api/v1/marketplace/collection?"+query).status_code==422

async def test_made_offers_filter_finds_older_records_beyond_the_first_chain_page(monkeypatch):
    from app.config import Settings
    import app.marketplace_api as m
    rows=[{"id":str(i),"token_id":"ECHO-000001" if i in (2,125) else "ECHO-000002","buyer":"buyer.near","seller":"owner.near"} for i in range(130)]
    class RPC:
        async def block(self):return {"hash":"pinned-block"}
        async def call(self,method,args):
            assert args["block_id"]=="pinned-block"
            p=json.loads(base64.b64decode(args["args_base64"]));page=rows[p["offset"]:p["offset"]+p["limit"]]
            return {"result":list(json.dumps(page).encode())}
    async def deployed():return {}
    monkeypatch.setattr(m,"settings",Settings(_env_file=None,near_market_contract="market.near"))
    monkeypatch.setattr(m,"deployed",deployed);monkeypatch.setattr(m,"rpc",lambda:RPC())
    result=await m.offers(offset=1,limit=1,token_id="ECHO-000001",account_id="buyer.near",scope="made")
    assert [o["id"] for o in result]==["125"]
    assert await m.offers(offset=0,limit=20,token_id="ECHO-000001",account_id="other.near",scope="received")==[]

async def test_duplicated_minted_tokens_are_rejected_instead_of_reporting_false_totals():
    class RPC:
        async def block(self):return {"hash":"block","height":2,"timestamp_nanosec":"100"}
        async def call(self,method,args):
            value={"nft_total_supply":"2","get_config":{},"nft_tokens":[token(1),token(1)],"get_listings":[]}[args["method_name"]]
            return {"result":list(json.dumps(value).encode())}
    with pytest.raises(ValueError,match="duplicated"):
        await collection_snapshot(RPC(),SimpleNamespace(near_nft_contract="nft.near",near_market_contract="market.near"))

async def test_auction_and_sold_filters_require_verified_custody_deadline_and_settlement():
    tokens=[token(1,"auction.near"),token(2,"winner.near"),token(3,"team.near"),token(4,"auction.near"),token(5,"auction.near"),token(6,"auction.near")]
    auctions=[]
    for i,status,end,bid,bidder,custody in [(1,"Active",200,"0",None,True),(2,"Settled",90,"100","winner.near",True),(3,"Unsold",90,"0",None,True),(4,"Active",100,"0",None,True),(5,"Active",200,"0",None,False),(6,"FundingPending",90,"100","winner.near",True)]:
        auctions.append({"token_id":f"ECHO-{i:06d}","status":status,"end_ns":str(end),"highest_bid":bid,"highest_bidder":bidder,"custody_verified":custody})
    class RPC:
        async def block(self):return {"hash":"one-final-block","height":1,"timestamp_nanosec":"100"}
        async def call(self,method,args):
            assert args["block_id"]=="one-final-block"
            if args["method_name"]=="get_auctions":
                p=json.loads(base64.b64decode(args["args_base64"]));assert p=={"from_index":0,"limit":100}
            value={"nft_total_supply":"6","nft_tokens":tokens,"get_listings":[],"get_config":{},"get_auctions":auctions}[args["method_name"]]
            return {"result":list(json.dumps(value).encode())}
    s=await collection_snapshot(RPC(),SimpleNamespace(near_nft_contract="nft.near",near_market_contract="market.near",near_auction_contract="auction.near",near_creator_account="team.near"))
    assert s["stats"]["on_auction"]==s["stats"]["sold"]==s["stats"]["unsold"]==1
    for status,expected in [("auction","ECHO-000001"),("sold","ECHO-000002"),("unsold","ECHO-000003")]:
        p=collection_page(s,status=status);assert p["total"]==1 and p["items"][0]["nft"]["token_id"]==expected
    assert collection_page(s,status="unsold")["items"][0]["returned_to_team"] is True
