import asyncio,re,time
from fastapi import APIRouter,HTTPException,Query
from .config import settings
from .services.near_rpc import NearRPC
from .services.reward_cycles import reward_snapshot

router=APIRouter(prefix="/api/v1/economy")
_cache={};_lock=asyncio.Lock()

@router.get("/cycles")
async def cycles(offset:int=Query(0,ge=0,le=10000),limit:int=Query(12,ge=1,le=36),fresh:bool=False):
    if not settings.near_nft_contract:return {"status":"not_deployed","network":settings.near_network,"months":[],"total":0,"block_height":None,"as_of_ns":None}
    if not re.fullmatch(r"[a-f0-9]{64}",settings.expected_nft_code_hash):raise HTTPException(409,"Pin the reviewed NFT contract before reading rewards")
    key=(settings.near_network,settings.near_rpc_url,settings.near_nft_contract,settings.expected_nft_code_hash)
    async with _lock:
        cached=_cache.get(key)
        if not fresh and cached and cached[0]>time.monotonic():result=cached[1]
        else:
            try:result=await reward_snapshot(settings,NearRPC(settings.near_rpc_url,budget_seconds=15))
            except Exception:raise HTTPException(503,"Monthly rewards could not be verified. Try again shortly.") from None
            _cache.clear();_cache[key]=(time.monotonic()+10,result)
    return {**result,"months":result["months"][offset:offset+limit],"total":len(result["months"]),"offset":offset,"limit":limit}
