import asyncio
import time
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from .config import settings
from .services.near_rpc import NearRPC
from .services.marketplace import validate_market,OneClick,account,checkout_amount

router=APIRouter(prefix="/api/v1/marketplace")
_validated={}
_validation_lock=asyncio.Lock()
_collection_cache={}
_collection_lock=asyncio.Lock()
def rpc():return NearRPC(settings.near_rpc_url)
async def deployed(fresh=False):
    if not settings.near_market_contract:raise HTTPException(409,"Marketplace is not deployed")
    key=(settings.near_market_contract,settings.expected_market_code_hash,settings.near_nft_contract,settings.expected_nft_code_hash,settings.near_creator_account,settings.near_auction_contract,settings.near_rpc_url,settings.near_network)
    async with _validation_lock:
        cached=_validated.get(key)
        if not fresh and cached and cached[0]>time.monotonic():return cached[1]
        result=await validate_market(settings,rpc());_validated.clear();_validated[key]=(time.monotonic()+30,result);return result

@router.get("")
async def config():
    if not settings.near_market_contract:return {"status":"not_deployed","contract":"","fee_bps":500,"crosschain":False}
    c=await deployed()
    return {**c,"status":"onchain","contract":settings.near_market_contract,"crosschain":settings.marketplace_crosschain_enabled and settings.near_network=="mainnet" and settings.execution_mode=="live"}

@router.get("/listings")
async def listings(offset:int=0,limit:int=20):
    bounds(offset,limit)
    if not settings.near_market_contract:return []
    await deployed();return await rpc().view(settings.near_market_contract,"get_listings",{"offset":offset,"limit":limit})

@router.get("/collection")
async def collection(offset:int=0,limit:int=20,search:str="",status:str="all",owner:str="",family:str="",sort:str="newest"):
    from .services.collection_market import collection_snapshot,collection_page
    bounds(offset,limit)
    if len(search)>120 or len(family)>160 or status not in ("all","listed","unlisted","auction","sold","unsold") or sort not in ("newest","price"):
        raise HTTPException(422,"Invalid collection filter")
    if owner:
        try:account(owner)
        except ValueError:raise HTTPException(422,"Invalid owner") from None
    if not settings.near_market_contract:
        return {"items":[],"total":0,"stats":{"items":0,"listed":0,"on_auction":0,"sold":0,"unsold":0,"owners":0,"floor":None},"families":[],"block_height":None}
    await deployed()
    key=(settings.near_rpc_url,settings.near_market_contract,settings.near_nft_contract,settings.expected_nft_code_hash,settings.expected_market_code_hash,settings.near_auction_contract,settings.expected_auction_code_hash,settings.near_creator_account)
    async with _collection_lock:
        cached=_collection_cache.get(key)
        if cached and cached[0]>time.monotonic():snapshot=cached[1]
        else:
            try:snapshot=await collection_snapshot(rpc(),settings)
            except Exception:raise HTTPException(503,"Collection could not be verified. Try again shortly.") from None
            _collection_cache.clear();_collection_cache[key]=(time.monotonic()+10,snapshot)
    return collection_page(snapshot,offset=offset,limit=limit,search=search,status=status,owner=owner,family=family,sort=sort)

@router.get("/offers")
async def offers(offset:int=0,limit:int=20,token_id:str="",account_id:str="",scope:str="all"):
    bounds(offset,limit)
    if not settings.near_market_contract:return []
    if len(token_id)>64 or scope not in ("all","made","received"):raise HTTPException(422,"Invalid offer filter")
    if account_id:
        try:account(account_id)
        except ValueError:raise HTTPException(422,"Invalid account") from None
    if scope!="all" and not account_id:raise HTTPException(422,"Connect an account to filter offers")
    await deployed();r=rpc()
    if not token_id and scope=="all":return await r.view(settings.near_market_contract,"get_offers",{"offset":offset,"limit":limit})
    # Filter the complete offer set before paginating, including older offers.
    block=await r.block();rows=[]
    import base64,json
    for start in range(0,10100,100):
        result=await r.call("query",{"request_type":"call_function","block_id":block["hash"],"account_id":settings.near_market_contract,
            "method_name":"get_offers","args_base64":base64.b64encode(json.dumps({"offset":start,"limit":100}).encode()).decode()})
        page=json.loads(bytes(result["result"]))
        if not isinstance(page,list) or len(page)>100 or len(rows)+len(page)>10000:raise HTTPException(503,"Offer collection exceeds query capacity")
        rows.extend(page)
        if len(page)<100:break
    rows=[o for o in rows if (not token_id or o["token_id"]==token_id) and (scope=="all" or o["buyer" if scope=="made" else "seller"]==account_id)]
    return rows[offset:offset+limit]

def bounds(offset,limit):
    if not 0<=offset<=100000 or not 1<=limit<=50:raise HTTPException(422,"Invalid pagination")

@router.get("/tokens")
async def tokens(offset:int=0,limit:int=20):
    bounds(offset,limit)
    if not settings.near_market_contract:return []
    await deployed();return await rpc().view(settings.near_nft_contract,"nft_tokens",{"from_index":str(offset),"limit":limit})

@router.get("/tokens/{token_id}")
async def token(token_id:str):
    if len(token_id)>64:raise HTTPException(422,"Invalid token")
    await deployed();r=rpc()
    nft,wallet,snapshot,listing,auction=await asyncio.gather(r.view(settings.near_nft_contract,"nft_token",{"token_id":token_id}),
        r.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token_id}),r.view(settings.near_nft_contract,"get_market_snapshot",{"token_id":token_id}),
        r.view(settings.near_market_contract,"get_listing",{"token_id":token_id}),
        r.view(settings.near_auction_contract,"get_auction",{"token_id":token_id}))
    if nft is None:raise HTTPException(404,"NFT not found")
    return {"nft":nft,"wallet":wallet,"snapshot":snapshot,"listing":listing,"auction":auction}

@router.get("/balances/{account_id}")
async def balance(account_id:str):
    account(account_id);await deployed();return await rpc().view(settings.near_market_contract,"get_balance",{"account":account_id})

@router.get("/funding/{account_id}")
async def funding(account_id:str):
    account(account_id);await deployed();r=rpc()
    native=await r.call("query",{"request_type":"view_account","account_id":account_id,"finality":"final"})
    wrapped=await r.view("wrap.near" if settings.near_network=="mainnet" else "wrap.testnet","ft_balance_of",{"account_id":account_id})
    return {"amount":native["amount"],"storage_usage":native["storage_usage"],"wrapped_near":wrapped}

@router.get("/royalties")
async def royalty_months(offset:int=0,limit:int=24):
    bounds(offset,limit)
    if not settings.near_market_contract:return []
    await deployed();return await rpc().view(settings.near_market_contract,"get_royalty_months",{"offset":offset,"limit":limit})

@router.get("/royalties/{cycle}/shares")
async def shares(cycle:int,offset:int=0,limit:int=25):
    bounds(offset,limit);await deployed();return await rpc().view(settings.near_market_contract,"get_royalty_shares",{"cycle":cycle,"offset":str(offset),"limit":limit})

def crosschain():
    if not settings.marketplace_crosschain_enabled or settings.near_network!="mainnet" or settings.execution_mode!="live":raise HTTPException(409,"Cross-chain checkout requires an enabled mainnet marketplace")

@router.get("/crosschain/tokens")
async def crosschain_tokens():
    crosschain();await deployed();return await OneClick(settings).tokens()

class FundingQuote(BaseModel):
    model_config=ConfigDict(extra="forbid")
    token_id:str=Field(min_length=1,max_length=64)
    listing_nonce:str=Field(pattern=r"^\d{1,20}$")
    buyer:str=Field(min_length=2,max_length=64)
    origin_asset:str=Field(min_length=1,max_length=200)
    refund_to:str=Field(min_length=1,max_length=256)
    offer_amount:str|None=Field(default=None,pattern=r"^[1-9]\d{0,32}$")
    dry:bool=True

@router.post("/crosschain/quote")
async def quote(body:FundingQuote):
    crosschain();await deployed(fresh=True);account(body.buyer)
    listing=await rpc().view(settings.near_market_contract,"get_listing",{"token_id":body.token_id})
    if not listing or str(listing["nonce"])!=body.listing_nonce:raise HTTPException(409,"Listing changed; refresh before funding")
    if listing["seller"]==body.buyer:raise HTTPException(422,"Seller cannot purchase own listing")
    nft=await rpc().view(settings.near_nft_contract,"nft_token",{"token_id":body.token_id})
    if not nft or nft["owner_id"]!=listing["seller"] or nft.get("approved_account_ids",{}).get(settings.near_market_contract)!=listing["approval_id"]:
        raise HTTPException(409,"Listing approval or ownership changed; do not fund this checkout")
    amount=checkout_amount(listing,body.offer_amount)
    value=await OneClick(settings).quote(origin_asset=body.origin_asset,buyer=body.buyer,refund_to=body.refund_to,amount=amount,dry=body.dry)
    return {"quote_response":value,"funding_yocto":str(amount),"purchase_executed":False,
        "notice":"Funds go to your NEAR wallet. The NFT is not reserved. After settlement, review the live listing and approve the purchase or offer. Keep any deposit memo exactly as provided."}

@router.get("/crosschain/status")
async def swap_status(deposit_address:str,deposit_memo:str|None=None):
    crosschain();await deployed()
    if not 1<=len(deposit_address)<=256 or deposit_memo is not None and len(deposit_memo)>256:raise HTTPException(422,"Invalid deposit details")
    return await OneClick(settings).request("GET","/status",params={"depositAddress":deposit_address,**({"depositMemo":deposit_memo} if deposit_memo is not None else {})})
