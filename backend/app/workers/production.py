"""One leased PostgreSQL worker per protocol; scheduled freeze, no late substitution."""
import asyncio
import json
import logging
import signal
import time
from datetime import datetime,timezone
from collections import Counter
from sqlalchemy import select,text
from ..config import settings
from ..database import init_db,Release,Observation,Artwork,Epoch,Effect,Job
from ..services.protocol import ensure_protocol
from ..services.storage import content_store
from ..services.canonical_data import snapshot,canonical,sha
from ..services.intents_collector import Collector
from ..services.randomness import fetch_beacon,select_timestamp
from ..services.near_rpc import NearRPC
from ..services.art_seed import GENESIS_HASH
from ..services.epoch_manager import run_epoch
from ..services.publication import publish,index_receipt
from ..services.chain_writer import ChainWriter
from ..services.chain_writer import OutcomeUnknown
from ..services.ingestion import persist_page
from ..services.preflight import validate_contracts,validate_source_rpc

log=logging.getLogger("echoes.worker")
WEEK=604800

def choose_observation(observations,freeze_at,max_age):
    eligible=sorted([o for o in observations if freeze_at-max_age<=o.completed_at<=freeze_at],key=lambda o:(o.completed_at,o.id),reverse=True)
    if len(eligible)<2:raise ValueError("No two complete observations within the published freeze window")
    if eligible[0].snapshot_hash!=eligible[1].snapshot_hash:raise ValueError("Latest reconciled observations disagree")
    return eligible[0]

class Worker:
    def __init__(self,factory,settings,clock=time.time,collector=None,rpc=None,beacon_fetch=fetch_beacon):
        self.factory,self.settings,self.clock=factory,settings,clock
        self.commitment,self.policy=ensure_protocol(factory,settings)
        self.store=content_store(settings)
        self.collector=collector or Collector(settings.near_intents_explorer_url,settings.near_intents_partner_jwt)
        self.rpc=rpc or NearRPC(settings.near_mainnet_rpc_url)
        self.fetch_beacon=beacon_fetch
        self.writer=ChainWriter(factory,settings)

    async def collect(self,*args,**kwargs):
        """Keep settlement/refunds moving during a long Explorer capture.

        Only the collector runs concurrently. All signing stays serialized in
        this leased worker; ambiguous signed outcomes stop this pass entirely.
        """
        task=asyncio.create_task(self.collector.collect(*args,**kwargs,statuses=("SUCCESS",)))
        try:
            while True:
                done,_=await asyncio.wait({task},timeout=self.settings.worker_poll_seconds)
                if done:return task.result()
                if self.settings.enable_chain_writes:
                    try:
                        await self.writer.reconcile_pending()
                        await self.monitor()
                    except OutcomeUnknown:raise
                    except Exception as exc:log.error("maintenance_delayed error_type=%s",type(exc).__name__)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)

    def release(self,number):
        with self.factory.begin() as db:
            r=db.get(Release,number)
            if not r:
                sunday=self.policy["first_sunday"]+(number-1)*WEEK
                r=Release(number=number,sunday=sunday,freeze_at=sunday+18*3600+self.settings.reconciliation_delay_seconds,state="scheduled",payload={"protocol_commitment":self.commitment},updated_at=int(self.clock()))
                db.add(r)
            db.flush();return r

    async def advance(self,number):
        r=self.release(number);now=int(self.clock())
        if r.state in ("auction_active","settled"):return
        if now<r.sunday+18*3600:return
        with self.factory() as db:
            previous=db.get(Artwork,f"live-{number-1:06d}") if number>1 else None
            prior_epoch=db.get(Epoch,previous.epoch_id) if previous else None
        if number>1 and previous is None:
            self.state(number,"delayed","PreviousEditionPending");return
        start_ns=int(prior_epoch.payload["end_ns"]) if prior_epoch else self.settings.genesis_checkpoint*10**9
        start=start_ns//10**9
        if "selection" not in r.payload:
            self.state(number,"selecting_checkpoint")
            beacon=await self.fetch_beacon(r.sunday+18*3600)
            target=select_timestamp(number,beacon["randomness"],r.sunday)
            block=await self.rpc.first_block_at(target)
            payload={**r.payload,"beacon":beacon,"block":block,"selection":{"sunday_start":r.sunday,"selected_timestamp":target,"algorithm":"selection-v1"}}
            with self.factory.begin() as db:
                row=db.get(Release,number);row.payload=payload;row.state="collecting"
            r.payload=payload
        block=r.payload["block"];end_ns=int(block["timestamp_ns"]);end=(end_ns+10**9-1)//10**9
        with self.factory() as db:art=db.get(Artwork,f"live-{number:06d}")
        if art:
            if not self.settings.enable_chain_writes:self.state(number,"awaiting_signer");return
            auction=await publish(self.factory,self.settings,art.payload,self.writer)
            self.state(number,"settled" if auction["status"] in ("Settled","Unsold","CreatorMinted") else "auction_active")
            return
        if now<r.freeze_at:
            from ..services.drop_progress import CollectionProgress
            progress=CollectionProgress(self.factory,number,self.clock)
            def on_page(page):
                persist_page(self.factory,page)
                progress.page(len(page))
            raw,evidence=await asyncio.wait_for(self.collect(start,end,self.settings.collector_page_size,on_page=on_page),max(1,r.freeze_at-int(self.clock())))
            completed=int(self.clock())
            if completed>r.freeze_at:
                self.state(number,"delayed","ObservationCompletedAfterFreeze");return
            records=snapshot(raw,start,end,start_ns=start_ns,end_ns=end_ns)
            progress.complete(len(raw),len(records))
            ref=self.store.put(canonical(records))
            source={**evidence,"classification":"authenticated_explorer_capture","snapshot_hash":ref["sha256"],"snapshot":ref,
                "observation_started_at":now,"observation_completed_at":completed,"status_counts":dict(Counter(x["status"] for x in raw)),
                "cutoff_ns":str(end_ns),"protocol_commitment":self.commitment}
            with self.factory.begin() as db:
                db.add(Observation(release_number=number,started_at=now,completed_at=completed,snapshot_hash=ref["sha256"],evidence=source))
            return
        with self.factory() as db:
            observations=list(db.scalars(select(Observation).where(Observation.release_number==number)))
        chosen=choose_observation(observations,r.freeze_at,self.settings.freeze_observation_max_age_seconds)
        records=json.loads(self.store.get(chosen.snapshot_hash))
        source={**chosen.evidence,"reconciled":True,"freeze_timestamp":r.freeze_at,
            "freeze_policy":self.policy["freeze_policy"],"observations":len(observations)}
        self.state(number,"rendering")
        art=await run_epoch(self.factory,self.settings,number=number,mode="live",raw=[],sealed_records=records,start=start,end=end,
            start_ns=start_ns,end_ns=end_ns,block=block,beacon=r.payload["beacon"],selection=r.payload["selection"],source=source,
            previous_hash=previous.image_hash if previous else GENESIS_HASH,evidence_rpc=self.rpc)
        self.state(number,"rendered")

    def state(self,number,state,error=None):
        with self.factory.begin() as db:
            r=db.get(Release,number);r.state=state;r.error=error;r.updated_at=int(self.clock())

    async def tick(self):
        if self.settings.enable_chain_writes:await self.writer.reconcile_pending()
        await self.monitor()
        now=int(self.clock())
        latest=max(1,(now-self.policy["first_sunday"])//WEEK+1)
        for n in range(1,latest+1):
            r=self.release(n)
            if r.state=="settled":continue
            try:await self.advance(n)
            except OutcomeUnknown:raise
            except Exception as exc:
                self.state(n,"delayed",type(exc).__name__)
                log.error("release_delayed epoch=%s error_type=%s",n,type(exc).__name__)
        await self.monitor()
        with self.factory() as db:
            if db.scalar(select(Release.number).where(Release.freeze_at>now,Release.sunday+18*3600<=now).limit(1)):
                return  # Preserve the fixed observation window for complete reconciliation passes.
        # Between release windows, keep a reconciled public feature index. It is
        # informational only: sealing always uses complete cutoff observations.
        with self.factory() as db:
            job=db.get(Job,"live-index")
            rows=list(db.scalars(select(Epoch).where(Epoch.mode=="live").order_by(Epoch.number.desc()).limit(1)))
        if job and now-job.updated_at<self.settings.index_poll_seconds:return
        start=int(rows[0].payload["end_ns"])//10**9 if rows else self.settings.genesis_checkpoint
        if start>=now:return
        with self.factory.begin() as db:
            job=db.get(Job,"live-index")
            if job is None:job=Job(key="live-index",kind="index_intents",status="running",attempts=0,payload={});db.add(job)
            job.status="running";job.attempts+=1;job.updated_at=now;job.error=None
        try:
            records,evidence=await self.collect(start,now,self.settings.collector_page_size,on_page=lambda page:persist_page(self.factory,page))
            with self.factory.begin() as db:
                job=db.get(Job,"live-index");job.status="succeeded";job.updated_at=int(self.clock());job.payload={"start":start,"end":now,"count":len(records),"evidence":evidence}
        except Exception as exc:
            with self.factory.begin() as db:
                job=db.get(Job,"live-index");job.status="failed";job.error=type(exc).__name__;job.updated_at=int(self.clock())
            raise

    async def monitor(self):
        if not self.settings.enable_chain_writes:return
        rpc=self.writer.rpc
        if self.settings.economy_enabled:
            from ..services.economy_keeper import EconomyKeeper
            await EconomyKeeper(self.factory,self.settings,self.writer).tick()
        latest=await rpc.block();now_ns=int(latest["timestamp_nanosec"])
        with self.factory() as db:arts=[a.payload for a in db.scalars(select(Artwork)) if a.payload["mode"]=="live" and a.payload["nft"]["status"]=="minted"]
        for art in arts:
            token=art["edition"];a=await rpc.view(self.settings.near_auction_contract,"get_auction",{"token_id":token})
            # EconomyKeeper owns v3 settlement/recovery. Do not issue a second
            # mutation under a different idempotency key in this same pass.
            if not self.settings.economy_enabled and a and a["status"]=="Active" and now_ns>=int(a["end_ns"]):
                receipt=await self.writer.submit(f'{art["id"]}:settle',self.settings.near_auction_contract,"finalize_auction",{"token_id":token})
                await index_receipt(self.factory,receipt,self.settings.near_auction_contract,token,rpc)
            elif not self.settings.economy_enabled and a and a["status"] in ("SettlementPending","RecoveryRequired"):
                receipt=await self.writer.submit(f'{art["id"]}:reconcile:{int(self.clock())//900}',self.settings.near_auction_contract,"reconcile_settlement",{"token_id":token})
                await index_receipt(self.factory,receipt,self.settings.near_auction_contract,token,rpc)
                recovered=await rpc.view(self.settings.near_auction_contract,"get_auction",{"token_id":token})
                if recovered["status"]=="RecoveryRequired":
                    with self.factory() as db:release=db.get(Release,art["number"]);attempts=release.payload.get("settlement_retries",0)
                    if attempts>=3:raise RuntimeError("Settlement recovery retry budget exhausted")
                    retry=await self.writer.submit(f'{art["id"]}:settle-retry:{attempts}',self.settings.near_auction_contract,"finalize_auction",{"token_id":token})
                    await index_receipt(self.factory,retry,self.settings.near_auction_contract,token,rpc)
                    with self.factory.begin() as db:
                        release=db.get(Release,art["number"]);release.payload={**release.payload,"settlement_retries":attempts+1}
            a=await rpc.view(self.settings.near_auction_contract,"get_auction",{"token_id":token})
            if a:
                with self.factory.begin() as db:
                    row=db.get(Artwork,art["id"]);row.payload={**row.payload,"auction":a}
                if a["status"] in ("Settled","Unsold"):self.state(art["number"],"settled")

async def main():
    if settings.execution_mode!="live" or settings.service_role!="worker":raise SystemExit("Worker requires SERVICE_ROLE=worker and EXECUTION_MODE=live")
    factory=init_db(create_schema=False)
    engine=factory.kw["bind"]
    if engine.dialect.name!="postgresql":raise SystemExit("The durable live worker requires PostgreSQL")
    # Session-level lock survives commits and is released on crash/disconnect.
    with engine.connect() as lease:
        if not lease.scalar(text("SELECT pg_try_advisory_lock(771862023)")):raise SystemExit("Another protocol worker owns the database lease")
        lease.commit()
        worker=Worker(factory,settings)
        await validate_contracts(settings)
        await validate_source_rpc(settings,worker.rpc)
        while True:
            if not lease.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid() AND classid=0 AND objid=771862023 AND granted)")):
                raise SystemExit("Worker no longer owns the database lease")
            lease.commit()
            task=asyncio.create_task(worker.tick())
            try:
                while not task.done():
                    await asyncio.wait({task},timeout=5)
                    try:
                        if not lease.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid() AND classid=0 AND objid=771862023 AND granted)")):raise RuntimeError("Lease lost")
                        lease.commit()
                    except Exception:
                        task.cancel()
                        raise SystemExit("Worker database lease lost; stopping all work") from None
                await task
            except Exception as exc:log.error("worker_tick_failed error_type=%s",type(exc).__name__)
            await asyncio.sleep(settings.worker_poll_seconds)

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(main())
