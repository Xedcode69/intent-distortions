import asyncio
import hmac
import json
import time
from threading import BoundedSemaphore
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select,text,func
from .config import settings
from .database import init_db, Artwork, Epoch, Job, Release, Swap, ChainEvent
from .services.epoch_manager import run_demo, sunday_schedule
from .services.storage import ContentStore,content_store
from .services.provenance import verify_artwork
from .services.merkle import verify as verify_merkle
from .services.randomness import verify_beacon, select_timestamp, round_for

factory = init_db()
store = content_store(settings)
verification_slots=BoundedSemaphore(settings.verification_concurrency)

def bounded_verification(artwork,rerender=False):
    if not verification_slots.acquire(blocking=False):
        raise HTTPException(429,"Verification capacity busy; retry shortly",headers={"Retry-After":"5"})
    try:return verify_artwork(store,artwork,rerender)
    finally:verification_slots.release()

@asynccontextmanager
async def lifespan(app):
    if settings.app_env=="production":
        from .services.protocol import ensure_protocol
        ensure_protocol(factory,settings)
    # Credential-free development bootstraps exactly one immutable demo edition.
    if settings.execution_mode=="demo" and settings.app_env=="development":
        await run_demo(factory,settings)
    task=None
    if settings.scheduler_enabled and settings.app_env!="production":
        from .workers.scheduler import scheduler
        task=asyncio.create_task(scheduler(factory,settings))
    yield
    if task:
        task.cancel()

app = FastAPI(title="NEAR ECHOES",version="1.0.0",lifespan=lifespan,
              docs_url=None if settings.app_env=="production" else "/docs",redoc_url=None if settings.app_env=="production" else "/redoc")
app.add_middleware(CORSMiddleware,allow_origins=[settings.cors_origin],allow_methods=["GET","POST"],allow_headers=["Content-Type","Authorization"])
from .middleware import RequestLimits,remove_demo_routes
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(RequestLimits,max_bytes=settings.max_request_bytes)
if settings.app_env=="production":app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.allowed_hosts)

@app.exception_handler(Exception)
async def unavailable(request,exc):
    import logging
    from fastapi.responses import JSONResponse
    logging.getLogger("echoes.api").error("request_failed error_type=%s",type(exc).__name__)
    return JSONResponse(status_code=503,content={"detail":"Service temporarily unavailable"})

@app.exception_handler(ValueError)
async def invalid(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422,content={"detail":str(exc)})

def art(id):
    with factory() as db:
        row=db.get(Artwork,id)
        if row is None or row.payload["mode"]!=settings.execution_mode:
            raise HTTPException(404,"Artwork not found")
        return row.payload

def all_art(limit=100,offset=0):
    with factory() as db:
        return [r.payload for r in db.scalars(select(Artwork).join(Epoch).where(Epoch.mode==settings.execution_mode).order_by(Epoch.number.desc()).limit(limit).offset(offset))]

def admin(request: Request):
    if not settings.admin_token or not hmac.compare_digest(request.headers.get("Authorization",""),f"Bearer {settings.admin_token}"):
        raise HTTPException(403,"Administrator token required")

def local_demo(request: Request):
    if settings.execution_mode!="demo" or settings.app_env!="development" or request.client.host not in ("127.0.0.1","::1","testclient"):
        raise HTTPException(404)
    # Reject browser cross-origin writes even on loopback (CSRF).
    origin=request.headers.get("origin")
    if origin and origin not in (settings.cors_origin,"http://127.0.0.1:3000"):
        raise HTTPException(403,"Origin not allowed")

@app.get("/api/v1/health")
def health():
    return {"status":"ok","mode":settings.execution_mode,"network":settings.near_network,
            "integrations":{"explorer":"recorded_capture" if settings.execution_mode=="historical_replay" else "worker_managed" if settings.app_env=="production" else "configured" if settings.near_intents_partner_jwt else "credentials_required",
            "near_ai":"recorded_direction" if settings.execution_mode=="historical_replay" else "worker_managed" if settings.app_env=="production" else "configured" if settings.near_ai_api_key else "deterministic_fallback",
            "nft":"configured" if settings.near_nft_contract else "not_deployed", "auction":"configured" if settings.near_auction_contract else "not_deployed"},
            "contracts":{"nft":settings.near_nft_contract,"auction":settings.near_auction_contract}}

@app.get("/readyz")
def ready():
    with factory() as db:
        db.execute(text("SELECT 1"))
        db.execute(select(Release.number).limit(1))
    return {"ready":True,"mode":settings.execution_mode}

@app.get("/api/v1/protocol")
def protocol_info():
    from .services.protocol import policy
    from .services.canonical_data import canonical,sha
    value=policy(settings)
    return {"policy":value,"commitment":sha(canonical(value)).hex(),"chain_writes_enabled":settings.enable_chain_writes}

@app.get("/api/v1/artworks")
def artworks(limit:int=50,offset:int=0):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,"Invalid page bounds")
    return all_art(limit,offset)

@app.get("/api/v1/artworks/latest")
def latest():
    rows=all_art()
    if not rows: raise HTTPException(404,"No artwork generated")
    return rows[0]

@app.get("/api/v1/artworks/{id}")
def artwork(id:str): return art(id)

@app.get("/api/v1/artworks/{id}/dna")
@app.get("/api/v1/artworks/{id}/manifest")
def dna(id:str): return json.loads(store.get(art(id)["manifest"]["sha256"]))

@app.get("/api/v1/artworks/{id}/verify")
def verify(id:str): return bounded_verification(art(id))

@app.get("/api/v1/epochs")
def epochs(limit:int=50,offset:int=0):
    if not 1<=limit<=100 or offset<0:raise HTTPException(422,"Invalid page bounds")
    with factory() as db:
        return [{"id":r.id,"number":r.number,"mode":r.mode,"status":r.status,"start":r.start,"end":r.end,"transaction_count":len(r.payload["records"])} for r in db.scalars(select(Epoch).where(Epoch.mode==settings.execution_mode).order_by(Epoch.number.desc()).limit(limit).offset(offset))]

@app.get("/api/v1/epochs/current")
def current():
    if settings.execution_mode=="historical_replay":
        with factory() as db:summary=db.get(Job,"historical-replay-summary")
        if summary:return summary.payload
        return {"mode":"historical_replay","status":"replay_not_loaded","next_selection":sunday_schedule(),
                "selected_block":None,"epoch_number":None,"indexed_records":0,"freeze_at":None,
                "collection":"historical_replay","schedule_timezone":"UTC"}
    if settings.execution_mode=="live":
        with factory() as db:
            r=db.scalar(select(Release).where(Release.state!="settled").order_by(Release.number).limit(1))
            count=db.scalar(select(func.count()).select_from(Swap))
            index=db.get(Job,"live-index")
        next_selection=sunday_schedule()
        if r and time.time()<r.sunday+18*3600:
            next_selection={"window_start":r.sunday,"window_end":r.sunday+17*3600,"beacon_at":r.sunday+18*3600}
        return {"mode":"live","status":r.state if r else "awaiting_checkpoint","next_selection":next_selection,
            "selected_block":r.payload.get("block") if r else None,"epoch_number":r.number if r else None,
            "freeze_at":r.freeze_at if r else None,"last_error_type":r.error if r else None,"indexed_records":count,
            "ingestion":{"status":index.status,"updated_at":index.updated_at,"error_type":index.error} if index else {"status":"not_started"},
            "collection":"authenticated_explorer","schedule_timezone":"UTC"}
    return {"mode":settings.execution_mode,"status":"demo_fixture" if settings.execution_mode=="demo" else "awaiting_checkpoint", "next_selection":sunday_schedule(),"selected_block":None,"collection":"not_live" if settings.execution_mode=="demo" else "see_ingestion_health", "schedule_timezone":"UTC"}


@app.get("/api/v1/replay/progress")
def replay_progress():
    if settings.execution_mode != "historical_replay" or settings.app_env == "production":
        raise HTTPException(404)
    from .services.replay_progress import read_progress
    try:
        return read_progress(settings.data_dir)
    except (ValueError, OSError):
        raise HTTPException(503,"Replay progress temporarily unavailable") from None

@app.get("/api/v1/epochs/{id}")
def epoch(id:str):
    with factory() as db:
        row=db.get(Epoch,id)
        if not row or row.mode!=settings.execution_mode: raise HTTPException(404)
        return {"id":row.id,"status":row.status,"start":row.start,"end":row.end,"transaction_count":len(row.payload["records"]),**{k:v for k,v in row.payload.items() if k!="records"}}

@app.get("/api/v1/epochs/{id}/statistics")
def epoch_stats(id:str): return art(id)["stats"]

@app.get("/api/v1/epochs/{id}/provenance")
def provenance(id:str): return json.loads(store.get(art(id)["provenance"]["sha256"]))

@app.get("/api/v1/content/{digest}")
def content(digest:str):
    if settings.app_env=="production" and settings.storage_provider=="s3":
        if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):raise HTTPException(422,"Invalid content hash")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f'{settings.artifact_public_url.rstrip("/")}/sha256/{digest}',status_code=307,headers={"Cache-Control":"public,max-age=31536000,immutable"})
    try: data=store.get(digest)
    except FileNotFoundError: raise HTTPException(404)
    kind="application/json"
    if data.startswith(b"\x89PNG"): kind="image/png"
    elif data.startswith(b"<svg"): kind="image/svg+xml"
    elif data.startswith(b"RIFF"): kind="image/webp"
    return Response(data,media_type=kind,headers={"Cache-Control":"public,max-age=31536000,immutable","X-Content-Type-Options":"nosniff","ETag":f'"{digest}"'})

@app.get("/api/v1/analytics/summary")
def summary():
    editions=swaps=minted=0
    with factory() as db:
        for row in db.scalars(select(Artwork).join(Epoch).where(Epoch.mode==settings.execution_mode).execution_options(yield_per=100)):
            editions+=1;swaps+=row.payload["stats"]["total_swaps"];minted+=row.payload["nft"]["status"]=="minted"
    return {"editions":editions,"swaps":swaps,"minted":minted,"mode":settings.execution_mode}

@app.get("/api/v1/analytics/chain-distribution")
def chains(): return latest()["stats"]["chains"]

@app.get("/api/v1/analytics/weekly-activity")
def activity(): return [{"edition":r["edition"],"count":r["stats"]["total_swaps"]} for r in all_art()]

@app.get("/api/v1/analytics/treasury")
async def treasury():
    if not settings.near_auction_contract:
        return {"status":"not_deployed","earned_yocto":"0","allocations":[],"events":[],"policy_bps":[2000,8000]}
    from .services.near_rpc import NearRPC
    if settings.economy_enabled:
        economy=await NearRPC(settings.near_rpc_url).view(settings.near_nft_contract,"get_economy",{})
        return {"status":"onchain","earned_yocto":economy["gross_earned"],"policy_bps":[2000,8000],"events":[],
            "allocations":[{"account":economy["treasury"],"balance":economy["treasury_credit"]}],"economy":economy}
    return await NearRPC(settings.near_rpc_url).view(settings.near_auction_contract,"get_treasury",{})

@app.get("/api/v1/economy")
async def economy():
    if not settings.near_nft_contract:
        return {"status":"not_deployed","currency":"NEAR","treasury_bps":2000,"vault_bps":8000,"early_exit_bps_of_vault":4000,
            "creator":None,"treasury":None,"treasury_earned":"0","treasury_credit":"0","next_close":202612,
            "first_edition_ns":"1794700800000000000","first_auction_ns":"1796515200000000000","exited_ticket_reentry":False}
    from .services.near_rpc import NearRPC
    return await NearRPC(settings.near_rpc_url).view(settings.near_nft_contract,"get_economy",{})

@app.get("/api/v1/economy/wallets")
async def edition_wallets(offset:int=0,limit:int=50):
    if offset<0 or not 1<=limit<=100:raise HTTPException(422,"Invalid pagination")
    if not settings.near_nft_contract:return []
    from .services.near_rpc import NearRPC
    return await NearRPC(settings.near_rpc_url).view(settings.near_nft_contract,"get_edition_wallets",{"from_index":offset,"limit":limit})

@app.get("/api/v1/economy/wallets/{token_id}")
async def edition_wallet(token_id:str):
    if not settings.near_nft_contract:raise HTTPException(404,"NFT contract not configured")
    from .services.near_rpc import NearRPC
    rpc=NearRPC(settings.near_rpc_url)
    wallet=await rpc.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token_id})
    if wallet is None:raise HTTPException(404,"Edition wallet not found")
    state=None
    if wallet["wallet_status"] not in ("Uncreated","Creating"):
        state=await rpc.view(wallet["account_id"],"get_state",{})
    token=await rpc.view(settings.near_nft_contract,"nft_token",{"token_id":token_id})
    return {**wallet,"vault_state":state,"current_owner":token["owner_id"] if token else None}

@app.get("/api/v1/economy/months")
async def economy_months(offset:int=0,limit:int=24):
    if offset<0 or not 1<=limit<=100:raise HTTPException(422,"Invalid pagination")
    if not settings.near_nft_contract:return []
    from .services.near_rpc import NearRPC
    return await NearRPC(settings.near_rpc_url).view(settings.near_nft_contract,"get_months",{"from_index":offset,"limit":limit})

@app.get("/api/v1/economy/months/{cycle}")
async def economy_month(cycle:int):
    if not 2026<=cycle//100<=2500 or not 1<=cycle%100<=12:raise HTTPException(422,"Invalid month")
    if not settings.near_nft_contract:raise HTTPException(404,"NFT contract not configured")
    from .services.near_rpc import NearRPC
    result=await NearRPC(settings.near_rpc_url).view(settings.near_nft_contract,"get_month",{"cycle":cycle})
    if result is None:raise HTTPException(404,"Monthly cycle not created")
    return result

@app.get("/api/v1/analytics/curation")
async def curation():
    if not settings.near_auction_contract:return {"token_id":None,"theme":"celestial","locked":True,"deadline_ns":"0"}
    from .services.near_rpc import NearRPC
    return await NearRPC(settings.near_rpc_url).view(settings.near_auction_contract,"get_theme",{})

@app.get("/api/v1/auctions")
async def auctions():
    if not settings.near_auction_contract: return []
    from .services.near_rpc import NearRPC
    return await NearRPC(settings.near_rpc_url).view(settings.near_auction_contract,"get_auctions",{})

@app.get("/api/v1/auctions/active")
async def active_auctions():
    return [a for a in await auctions() if a["status"]=="Active"]

@app.get("/api/v1/auctions/{id}")
async def auction(id:str):
    if not settings.near_auction_contract: raise HTTPException(404,"Auction contract is not configured")
    from .services.near_rpc import NearRPC
    token_id=art(id)["edition"]
    result=await NearRPC(settings.near_rpc_url).view(settings.near_auction_contract,"get_auction",{"token_id":token_id})
    if result is None: raise HTTPException(404)
    return result

@app.get("/api/v1/auctions/{id}/bids")
async def bids(id:str):
    await auction(id)
    token=art(id)["edition"]
    with factory() as db:
        rows=list(db.scalars(select(ChainEvent).where(ChainEvent.token_id==token,ChainEvent.kind=="bid").order_by(ChainEvent.block_height.desc()).limit(100)))
    return {"status":"indexed_receipts","bids":[{"transaction_hash":r.transaction_hash,"block_height":r.block_height,**r.payload} for r in rows],"coverage":"finalized receipts observed by the configured worker/indexer; not a completeness proof"}

class MerkleRequest(BaseModel):
    record:dict
    proof:list[dict]=Field(max_length=64)
    root:str=Field(pattern="^[0-9a-f]{64}$")

@app.post("/api/v1/verify/merkle-proof")
def merkle(request:MerkleRequest): return {"valid":verify_merkle(request.record,request.proof,request.root)}

class SelectionRequest(BaseModel):
    epoch:int=Field(ge=1)
    sunday_start:int=Field(ge=0)
    beacon:dict

@app.post("/api/v1/verify/block-selection")
def block_selection(request:SelectionRequest):
    from datetime import datetime, timezone
    date=datetime.fromtimestamp(request.sunday_start,timezone.utc)
    if date.weekday()!=6 or date.hour or date.minute or date.second: raise ValueError("Sunday 00:00 UTC required")
    beacon=verify_beacon(request.beacon,round_for(request.sunday_start+18*3600))
    return {"verified":True,"selected_timestamp":select_timestamp(request.epoch,beacon["randomness"],request.sunday_start),"scope":"Beacon signature and timestamp calculation; block predecessor proof separate"}

class ArtworkRequest(BaseModel):
    id:str
    rerender:bool=False

@app.post("/api/v1/verify/artwork")
def verify_supplied(request:ArtworkRequest,raw:Request):
    if settings.app_env=="production" and request.rerender:admin(raw)
    return bounded_verification(art(request.id),request.rerender)

class ReceiptRequest(BaseModel):
    transaction_hash:str=Field(pattern="^[1-9A-HJ-NP-Za-km-z]{40,44}$")
    sender:str=Field(pattern="^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$")

@app.post("/api/v1/receipts")
async def receipt(request:ReceiptRequest):
    if not settings.near_auction_contract:raise HTTPException(409,"Auction contract not configured")
    from .services.receipt_indexer import ingest
    return await ingest(factory,settings,request.transaction_hash,request.sender)

@app.post("/api/v1/demo/run-epoch",dependencies=[Depends(local_demo)])
async def demo(): return await run_demo(factory,settings)

@app.get("/api/v1/demo/status")
def demo_status(): return {"mode":settings.execution_mode,"reset_policy":"Frozen epochs cannot be reset through HTTP", "artworks":len(all_art())}

@app.get("/api/v1/admin/jobs",dependencies=[Depends(admin)])
def jobs():
    with factory() as db:
        return [{"key":j.key,"status":j.status,"attempts":j.attempts,"error":j.error} for j in db.scalars(select(Job))]

@app.get("/api/v1/admin/releases",dependencies=[Depends(admin)])
def releases():
    with factory() as db:
        return [{"number":r.number,"state":r.state,"freeze_at":r.freeze_at,"error_type":r.error,"updated_at":r.updated_at} for r in db.scalars(select(Release).order_by(Release.number.desc()).limit(100))]

if settings.app_env=="production":remove_demo_routes(app)
