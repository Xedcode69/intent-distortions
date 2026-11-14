import asyncio
import time
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from .config import settings
from .services.near_rpc import NearRPC
from .services.onchain_reader import snapshot,recover_asset

router=APIRouter(prefix="/api/v1/onchain")
_cache={};_lock=asyncio.Lock()

async def read(kind=None):
    if not settings.onchain_art_contract:raise HTTPException(404,"Onchain study has not been configured")
    key=(settings.near_rpc_url,settings.near_network,settings.onchain_art_contract,settings.onchain_art_token_id,settings.expected_onchain_art_code_hash)
    async with _lock:
        cached=_cache.get(key)
        try:
            rpc=NearRPC(settings.near_rpc_url,budget_seconds=20)
            if not cached or cached['expires']<time.monotonic():
                cached={'state':await snapshot(settings,rpc),'assets':{},'expires':time.monotonic()+30}
                _cache.clear();_cache[key]=cached
            if kind and kind not in cached['assets']:
                cached['assets'][kind]=await recover_asset(settings,rpc,cached['state'],kind)
            return cached['assets'][kind] if kind else cached['state']
        except Exception:
            raise HTTPException(503,"The onchain artwork could not be verified. Try again shortly.") from None

@router.get("/prototype")
async def prototype():return await read()

@router.get("/prototype/static.svg")
async def static_svg():return await svg(False)

@router.get("/prototype/animated.svg")
async def animated_svg():return await svg(True)

async def svg(animated):
    data=await read("animated" if animated else "static")
    return Response(data,media_type="image/svg+xml",headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff",
        "Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; sandbox"})

@router.get("/prototype/recipe.bin")
async def recipe():
    return Response(await read("recipe"),media_type="application/octet-stream",headers={"Cache-Control":"no-store",
        "Content-Disposition":'attachment; filename="intent-distortions-idart1.bin"',"X-Content-Type-Options":"nosniff"})
