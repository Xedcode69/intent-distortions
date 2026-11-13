"""Public drop schedule and persisted progress, independent of auction duration."""
import time
from datetime import datetime,timezone
from sqlalchemy import select,func
from ..database import Artwork,Epoch,Release,Job

WEEK=604800
GENERATION_PHASES={"art_direction","rendering","preparing_files","ready"}

def schedule(first,number,delay,release=None):
    sunday=first+(number-1)*WEEK
    if release is not None:sunday=release.sunday
    date=datetime.fromtimestamp(sunday,timezone.utc)
    return {"number":number,"edition":f"ECHO-{number:06d}","sunday":sunday,"beacon_at":sunday+18*3600,
        "window_start":sunday,"window_end":sunday+17*3600,
        "freeze_at":release.freeze_at if release else sunday+18*3600+delay,
        "delivery":"creator" if sunday<1796515200 else "auction","auction_hours":None if sunday<1796515200 else 24,
        "month":date.strftime("%B %Y")}

def artwork_summary(payload,details):
    return {**details,**{k:payload[k] for k in ("id","edition","number","mode","title","description","composition","image","thumbnail","image_hash","seed","start","end")},
        "records":payload["stats"]["total_swaps"],"source_networks":payload["stats"]["unique_chains"],
        "nft_status":payload["nft"]["status"],"auction_status":payload["auction"]["status"]}

def drop_feed(factory,settings,*,offset=0,limit=12,now=None):
    now=int(time.time()) if now is None else int(now)
    live=settings.execution_mode=="live"
    # Saved replay/fixture epoch numbering is not the production launch sequence.
    first_date=settings.first_release_sunday if live or not settings.economy_enabled else "2026-11-15"
    first=int(datetime.strptime(first_date,"%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    mode=settings.execution_mode
    with factory() as db:
        numbers=list(db.scalars(select(Epoch.number).join(Artwork,Artwork.epoch_id==Epoch.id).where(Epoch.mode==mode).order_by(Epoch.number)))
        number=1
        if live:
            for n in numbers:
                if n!=number:break
                number+=1
        else:
            number=max(1,(now-first)//WEEK+1)
            if now>=schedule(first,number,settings.reconciliation_delay_seconds)["freeze_at"]:number+=1
        r=db.get(Release,number) if live else None
        upcoming=schedule(first,number,settings.reconciliation_delay_seconds,r)
        active=None;focus=r
        if live and (r and r.state!="scheduled" or now>=upcoming["beacon_at"]):
            active={**upcoming,"artwork":None}
        latest=db.scalar(select(Artwork).join(Epoch).where(Epoch.mode==mode).order_by(Epoch.number.desc()).limit(1))
        if live and active is None and latest:
            focus=db.get(Release,latest.payload["number"])
            info=schedule(first,latest.payload["number"],settings.reconciliation_delay_seconds,focus)
            active={**info,"artwork":artwork_summary(latest.payload,info)}
        if active is not None:
            n=active["number"]
            progress=db.get(Job,f"drop:{n}:collection")
            generation=db.get(Job,f"live-{n:06d}:generate-v1")
            state=focus.state if focus else "artwork_ready" if active["artwork"] else "awaiting_worker"
            phase="ready" if active["artwork"] else "awaiting_worker" if state in ("scheduled","awaiting_worker") else "checkpoint"
            if active["artwork"] is None:
                if generation and generation.payload.get("phase") in GENERATION_PHASES:phase=generation.payload["phase"]
                elif state in ("rendering","rendered"):phase="rendering"
                elif progress:phase="reconciliation" if progress.payload.get("collection_complete") else "collection"
                elif state=="collecting":phase="collection"
            public={key:progress.payload.get(key) for key in ("received_rows","pages","total_records","eligible_records","collection_complete")} if progress else {}
            active.update(state=state,phase=phase,last_error_type=focus.error if focus else None,
                progress={"pass_number":progress.attempts if progress else 0,**public,"updated_at":max([j.updated_at for j in (progress,generation,focus) if j is not None],default=None)},
                selected_block={k:focus.payload["block"].get(k) for k in ("height","hash")} if focus and focus.payload.get("block") else None)
        archive=select(Artwork).join(Epoch).where(Epoch.mode==mode)
        if active and active["artwork"]:archive=archive.where(Artwork.id!=active["artwork"]["id"])
        total=db.scalar(select(func.count()).select_from(archive.subquery()))
        rows=list(db.scalars(archive.order_by(Epoch.number.desc()).offset(offset).limit(limit)))
        previous=[]
        for row in rows:
            if live:
                info=schedule(first,row.payload["number"],settings.reconciliation_delay_seconds,db.get(Release,row.payload["number"]))
            else:
                # Replay/fixture release dates come from their recorded epoch.
                sunday=db.scalar(select(Epoch.payload["selection"]["sunday_start"].as_integer()).where(Epoch.id==row.epoch_id))
                info=schedule(int(sunday)-(row.payload["number"]-1)*WEEK if sunday is not None else first,row.payload["number"],settings.reconciliation_delay_seconds)
            previous.append(artwork_summary(row.payload,info))
    return {"mode":mode,"as_of":now,"schedule_timezone":"UTC","preview":not live,
        "upcoming":upcoming,"active":active,"previous":previous,"total_previous":total,"offset":offset,"limit":limit}
