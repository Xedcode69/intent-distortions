import asyncio,base64,hashlib,json,re
import base58
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

@router.get("/editions/{token_id}/{asset}")
async def edition_asset(token_id:str,asset:str):
    """Recover frozen media from a single finalized block; no local image fallback."""
    if not re.fullmatch(r"ECHO-\d{6}",token_id) or asset not in ("static.svg","animated.svg","recipe.bin","provenance.json"):
        raise HTTPException(404)
    key=(settings.near_rpc_url,settings.near_nft_contract,settings.expected_nft_code_hash,token_id,asset)
    async with _lock:
        cached=_cache.get(key)
        if cached and cached["expires"]>time.monotonic():data=cached["data"]
        else:
            try:
                rpc=NearRPC(settings.near_rpc_url,budget_seconds=30);block=await rpc.block()
                async def view(method,args):
                    result=await rpc.call("query",{"request_type":"call_function","block_id":block["hash"],"account_id":settings.near_nft_contract,
                        "method_name":method,"args_base64":base64.b64encode(json.dumps(args).encode()).decode()})
                    return json.loads(bytes(result["result"]))
                chain,code,keys,state=await asyncio.gather(rpc.call("status",{}),
                    rpc.call("query",{"request_type":"view_account","block_id":block["hash"],"account_id":settings.near_nft_contract}),
                    rpc.call("query",{"request_type":"view_access_key_list","block_id":block["hash"],"account_id":settings.near_nft_contract}),
                    view("get_onchain_art",{"token_id":token_id}))
                if chain["chain_id"]!="testnet" or not re.fullmatch(r"[a-f0-9]{64}",settings.expected_nft_code_hash) \
                    or base58.b58decode(code["code_hash"]).hex()!=settings.expected_nft_code_hash or keys.get("keys")!=[]:
                    raise ValueError("Immutable collection identity mismatch")
                if not state or state["format"]!="intent-distortions-weekly-onchain-v1" or not state["sealed"]:
                    raise ValueError("Edition not sealed")
                if asset=="provenance.json":
                    token=await view("nft_token_compact",{"token_id":token_id})
                    reference=token["metadata"]["reference"]
                    if not reference.startswith("data:application/json;base64,"):raise ValueError("Inline provenance required")
                    data=base64.b64decode(reference.split(",",1)[1],validate=True);expected=state["commitment"]["provenance_hash"]
                elif asset=="recipe.bin":
                    if not 76<state["recipe_bytes"]<=262144:raise ValueError("Recipe budget")
                    chunks=[]
                    for start in range(0,state["recipe_bytes"],16384):
                        chunk=base64.b64decode(await view("get_recipe_chunk",{"token_id":token_id,"offset":start}),validate=True)
                        if len(chunk)!=min(16384,state["recipe_bytes"]-start):raise ValueError("Incomplete recipe")
                        chunks.append(chunk)
                    data=b"".join(chunks);expected=state["recipe_sha256"]
                else:
                    kind=asset.split(".",1)[0];svg=await view("get_"+kind+"_svg",{"token_id":token_id})
                    if not isinstance(svg,str) or not svg.startswith("<svg ") or len(svg)>2_000_000:raise ValueError("SVG budget")
                    data=svg.encode();expected=state[kind+"_sha256"]
                if hashlib.sha256(data).hexdigest()!=expected:raise ValueError("Frozen asset hash mismatch")
                if len(_cache)>32:_cache.clear()
                _cache[key]={"data":data,"expires":time.monotonic()+30}
            except Exception:raise HTTPException(503,"The onchain artwork could not be verified. Try again shortly.") from None
    media="image/svg+xml" if asset.endswith(".svg") else "application/json" if asset.endswith(".json") else "application/octet-stream"
    return Response(data,media_type=media,headers={"Cache-Control":"public,max-age=30","X-Content-Type-Options":"nosniff",
        "Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; sandbox"})
