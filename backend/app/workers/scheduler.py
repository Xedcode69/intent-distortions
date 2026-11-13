"""Single process, DB-persisted ingestion jobs. Weekly release fails closed."""
import asyncio
import time
from sqlalchemy import select
from ..database import Job, Swap
from ..services.intents_collector import Collector
from ..services.canonical_data import normalize, record_key

async def sync(factory,settings,start,end):
    collector=Collector(settings.near_intents_explorer_url,settings.near_intents_partner_jwt)
    key=f"sync:{start}:{end}"
    with factory.begin() as db:
        job=db.get(Job,key)
        if job is None:
            job=Job(key=key,kind="sync_intents",status="pending",attempts=0,payload={"start":start,"end":end}); db.add(job)
        if job.status=="succeeded": return job.payload
        job.status="running"; job.attempts+=1; job.updated_at=int(time.time())
    def persist(page):
        with factory.begin() as db:
            for raw in page:
                normalized=normalize(raw); key=record_key(raw)
                row=db.get(Swap,key)
                if row and (row.created_at_unix!=normalized["created_at_unix"] or row.normalized["origin_asset"]!=normalized["origin_asset"] or row.normalized["destination_asset"]!=normalized["destination_asset"]):
                    raise ValueError("Record identity conflict")
                if row is None:
                    row=Swap(key=key,created_at_unix=normalized["created_at_unix"],status=raw["status"],normalized=normalized,last_verified_at=int(time.time())); db.add(row)
                else:
                    row.normalized=normalized; row.status=raw["status"]; row.last_verified_at=int(time.time())
    try:
        records,evidence=await collector.collect(start,end,on_page=persist)
        with factory.begin() as db:
            job=db.get(Job,key); job.status="succeeded"; job.payload={"start":start,"end":end,"evidence":evidence,"count":len(records)}
        return records,evidence
    except Exception as exc:
        with factory.begin() as db:
            job=db.get(Job,key); job.status="failed"; job.error=type(exc).__name__
        raise

async def scheduler(factory,settings):
    if settings.execution_mode!="live": return
    while True:
        end=int(time.time())
        try:
            # Full current epoch replay reconciles pending statuses and late arrivals.
            await sync(factory,settings,settings.genesis_checkpoint,end)
        except Exception:
            pass  # durable job contains failure; no mint or fabricated release
        await asyncio.sleep(60)
