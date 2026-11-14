"""Collection-wide ordering from one finalized block, before filtering/pagination."""
import asyncio
import base64
import json

MAX_ITEMS = 10000  # Over 190 years of weekly editions; fail rather than truncate.


async def collection_snapshot(rpc, settings):
    block = await rpc.block()
    async def view(contract, method, args):
        result = await rpc.call("query", {"request_type": "call_function", "block_id": block["hash"],
            "account_id": contract, "method_name": method,
            "args_base64": base64.b64encode(json.dumps(args).encode()).decode()})
        return json.loads(bytes(result["result"]))

    async def pages(contract, method, nft=False, from_index=False):
        rows = []
        for offset in range(0, MAX_ITEMS + 100, 100):
            args = {"from_index": str(offset), "limit": 100} if nft else {"offset": offset, "limit": 100}
            if from_index:args={"from_index":offset,"limit":100}
            page = await view(contract, method, args)
            if not isinstance(page, list) or len(page) > 100:
                raise ValueError("Invalid collection page")
            rows.extend(page)
            if len(rows) > MAX_ITEMS:
                raise ValueError("Collection exceeds snapshot capacity")
            if len(page) < 100:
                return rows
        raise ValueError("Incomplete collection")

    tokens, listings, config, supply = await asyncio.gather(
        pages(settings.near_nft_contract, "nft_tokens", True),
        pages(settings.near_market_contract, "get_listings"),
        view(settings.near_market_contract, "get_config", {}),
        view(settings.near_nft_contract, "nft_total_supply", {}))
    if not isinstance(supply,str) or not supply.isdecimal() or int(supply)!=len(tokens) or len({t["token_id"] for t in tokens})!=len(tokens):
        raise ValueError("Incomplete or duplicated minted collection")
    now_ns = int(config.get("clock_ns") or block["timestamp_nanosec"])
    auction_contract=getattr(settings,"near_auction_contract","")
    auctions=await pages(auction_contract,"get_auctions",from_index=True) if auction_contract else []
    auction_by_id={a["token_id"]:a for a in auctions}
    by_id = {l["token_id"]: l for l in listings}
    items = []
    for token in tokens:
        auction=auction_by_id.get(token["token_id"])
        in_custody=token["owner_id"]==auction_contract
        on_auction=bool(auction and auction["status"]=="Active" and auction["custody_verified"] and int(auction["end_ns"])>now_ns and in_custody)
        sold=bool(auction and auction["status"]=="Settled" and int(auction["highest_bid"])>0 and auction.get("highest_bidder") and not in_custody)
        unsold=bool(auction and auction["status"]=="Unsold" and int(auction["highest_bid"])==0 and not auction.get("highest_bidder"))
        listing = by_id.get(token["token_id"])
        active = bool(listing and not listing["sale"] and int(listing["expires_ns"]) > now_ns
            and listing["seller"] == token["owner_id"]
            and token.get("approved_account_ids", {}).get(settings.near_market_contract) == listing["approval_id"])
        try:
            extra = json.loads(token.get("metadata", {}).get("extra") or "{}")
            attrs = extra.get("attributes", [])
            family = next((str(a["value"]) for a in attrs if a.get("trait_type") in ("Family", "Composition", "Art family", "Composition family")), "Other")
        except (ValueError, TypeError, AttributeError, KeyError):
            family = "Other"
        items.append({"nft": token, "listing": listing if active else None, "family": family,
            "auction":auction,"on_auction":on_auction,"sold":sold,"unsold":unsold,
            "returned_to_team":unsold and token["owner_id"]==getattr(settings,"near_creator_account","")})
    prices = [int(i["listing"]["price"]) for i in items if i["listing"] and i["listing"]["price"]]
    return {"items": items, "block_height": block["height"], "stats": {
        "items": len(items), "listed": sum(i["listing"] is not None for i in items),
        "on_auction":sum(i["on_auction"] for i in items),"sold":sum(i["sold"] for i in items),"unsold":sum(i["unsold"] for i in items),
        "owners": len({i["nft"]["owner_id"] for i in items}), "floor": str(min(prices)) if prices else None},
        "families": sorted({i["family"] for i in items})}


def collection_page(snapshot, *, offset=0, limit=20, search="", status="all", owner="", family="", sort="newest"):
    def matches(item):
        nft, listing = item["nft"], item["listing"]
        matches_status={"all":True,"listed":bool(listing),"unlisted":not listing,"auction":item["on_auction"],"sold":item["sold"],"unsold":item["unsold"]}.get(status,False)
        return (not owner or nft["owner_id"] == owner) and (not family or item["family"] == family) \
            and matches_status \
            and search.casefold() in f'{nft["token_id"]} {nft.get("metadata", {}).get("title", "")} {item["family"]}'.casefold()
    items = [i for i in snapshot["items"] if matches(i)]
    # Stable secondary order, then active listings first for every sort choice.
    items.sort(key=lambda i: i["nft"]["token_id"], reverse=True)
    if sort == "price":
        items.sort(key=lambda i: int(i["listing"]["price"]) if i["listing"] and i["listing"]["price"] else 10**40)
    items.sort(key=lambda i: i["listing"] is None)
    return {**snapshot, "items": items[offset:offset+limit], "total": len(items), "offset": offset, "limit": limit}
