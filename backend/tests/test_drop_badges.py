import base64,copy,json
from app.services.drops import mark_drop_ownership

def art(i):return {"edition":f"ECHO-{i:06d}","image_hash":"ab"*32,"nft_status":"minted","auction_status":"old","sunday":1}
def item(i,owner="collector.testnet",**updates):
    return {"nft":{"token_id":f"ECHO-{i:06d}","owner_id":owner,"metadata":{"media_hash":base64.b64encode(bytes.fromhex("ab"*32)).decode(),"extra":json.dumps({"release_ns":"1798934400000000000"})}},"on_auction":False,"sold":False,"auction":None,**updates}

def test_badges_follow_current_team_ownership_and_verified_auction_state():
    feed={"previous":[art(i) for i in range(1,5)],"active":None}
    snapshot={"items":[item(1,"team.testnet"),item(2,"auction.testnet",on_auction=True,auction={"status":"Active"}),item(3,sold=True,auction={"status":"Settled"}),item(4,"team.testnet",sold=True,auction={"status":"Settled"})]}
    result=mark_drop_ownership(feed,snapshot,"team.testnet")
    assert [a["display_status"] for a in result["previous"]]==["reserved","on_auction","sold","reserved"]
    assert result["previous"][0]["sunday"]==1798934400
    assert result["previous"][0]["image_hash"]=="ab"*32

def test_a_study_or_mismatched_image_never_acquires_another_tokens_badge():
    feed={"previous":[art(1),art(2)],"active":None}
    wrong=item(1,"team.testnet");wrong["nft"]["metadata"]["media_hash"]="wrong hash"
    result=mark_drop_ownership(feed,{"items":[wrong]},"team.testnet")
    assert all(a["display_status"] is None for a in result["previous"])
    result=mark_drop_ownership({"previous":[art(1)],"active":None},None,"team.testnet")
    assert result["chain_status"]=="unavailable" and result["previous"][0]["display_status"] is None
