import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import select,insert
from ..database import Epoch, Artwork, EpochTransaction, Job
from ..config import ROOT
from .canonical_data import canonical, sha, snapshot,validate_snapshot
from .merkle import root, proof,proof_index
from .art_seed import master_seed, GENESIS_HASH
from .art_statistics import statistics
from .art_renderer import scene, render
from .near_ai import creative_direction,apply_curatorial_theme
from .storage import ContentStore,content_store

def sunday_schedule(now=None):
    now = now or datetime.now(timezone.utc)
    day = now.replace(hour=0,minute=0,second=0,microsecond=0)
    sunday = day + timedelta(days=(6-day.weekday())%7)
    if now >= sunday+timedelta(hours=18):
        sunday += timedelta(days=7)
    return {"window_start": int(sunday.timestamp()), "window_end":int((sunday+timedelta(hours=17)).timestamp()),
            "beacon_at":int((sunday+timedelta(hours=18)).timestamp())}

async def run_epoch(factory, settings, *, number, mode, raw, start, end, block, beacon,
                    selection, source, previous_hash=GENESIS_HASH, start_ns=None, end_ns=None, sealed_records=None, evidence_rpc=None,
                    asset_mapping=None):
    if mode != settings.execution_mode:
        raise ValueError("Execution mode mismatch")
    if mode != "demo":
        if not source.get("complete") or not source.get("reconciled"):
            raise ValueError("Incomplete/reconciliation-pending epoch must not freeze")
        from .randomness import verify_beacon,round_for,select_timestamp
        from .near_rpc import NearRPC
        sunday=selection["sunday_start"]
        from datetime import datetime,timezone
        date=datetime.fromtimestamp(sunday,timezone.utc)
        if date.weekday()!=6 or date.hour or date.minute or date.second:
            raise ValueError("Selection schedule must begin Sunday 00:00 UTC")
        beacon=verify_beacon(beacon,round_for(sunday+18*3600))
        target=select_timestamp(number,beacon["randomness"],sunday)
        if selection["selected_timestamp"]!=target:
            raise ValueError("Selection evidence mismatch")
        await (evidence_rpc or NearRPC(settings.near_mainnet_rpc_url)).verify_selected_block(block,target)
        end_ns=int(block["timestamp_ns"])
    epoch_id = f"{mode}-{number:06d}"
    key = f"{epoch_id}:generate-v1"
    store = content_store(settings)
    if sealed_records is not None:
        records=validate_snapshot(sealed_records,start_ns or start*10**9,end_ns or end*10**9)
        if sha(canonical(records)).hex()!=source.get("snapshot_hash"):raise ValueError("Sealed observation hash mismatch")
    else:records = snapshot(raw,start,end,start_ns=start_ns,end_ns=end_ns)
    from .asset_networks import fetch_asset_mapping, validate_asset_mapping, mapped_seed
    with factory() as db:
        saved_art=db.get(Artwork,epoch_id)
        saved_epoch=db.get(Epoch,epoch_id)
        if saved_art:
            if asset_mapping is not None and (saved_epoch is None or saved_epoch.payload.get("asset_mapping")!=asset_mapping):
                raise ValueError("Frozen network mapping cannot change")
            return saved_art.payload
        prior_mapping=saved_epoch.payload.get("asset_mapping") if saved_epoch is not None else None
        has_epoch=saved_epoch is not None
    if has_epoch:
        if asset_mapping is not None and asset_mapping!=prior_mapping:
            raise ValueError("Frozen network mapping cannot change")
        asset_mapping=prior_mapping
    elif asset_mapping is None and mode!="demo":
        asset_mapping=await fetch_asset_mapping(records)
    if asset_mapping is not None:
        validate_asset_mapping(asset_mapping,records)
    # Lock and persist exact inputs before calling AI or rendering. A restart reuses
    # the snapshot and first persisted direction, never operator-supplied rerolls.
    with factory.begin() as db:
        existing_art = db.get(Artwork,epoch_id)
        if existing_art:
            return existing_art.payload
        job = db.get(Job,key,with_for_update=True)
        if job is None:
            job = Job(key=key,kind="generate_epoch",status="pending",attempts=0,payload={})
            db.add(job)
        if job.status == "running" and int(time.time())-job.updated_at < 600:
            raise ValueError("Epoch job already running")
        epoch = db.get(Epoch,epoch_id)
        if epoch is None:
            if mode=="live":
                from .protocol import ensure_protocol
                # Policy is already committed by the worker before observation.
                from ..database import Protocol
                policy_row=db.get(Protocol,"active")
                if policy_row is None:raise ValueError("Live protocol policy was not committed")
                if source.get("classification")!="authenticated_explorer_capture":raise ValueError("Live editions require authenticated Explorer observations")
                if number==1:
                    if start_ns not in (None,settings.genesis_checkpoint*10**9):raise ValueError("Invalid genesis checkpoint")
                    if start!=settings.genesis_checkpoint or previous_hash!=GENESIS_HASH:raise ValueError("Invalid genesis lineage")
                else:
                    prior=db.get(Artwork,f"live-{number-1:06d}")
                    if prior is None:raise ValueError("Previous canonical edition is required")
                    prior_epoch=db.get(Epoch,prior.epoch_id)
                    if previous_hash!=prior.image_hash or str(start_ns)!=prior_epoch.payload["end_ns"]:raise ValueError("Consecutive checkpoint lineage mismatch")
            snapshot_ref = store.put(canonical(records))
            payload = {"snapshot":snapshot_ref,"records":records,"block":block,"beacon":beacon,
                       "selection":selection,"source":source,"previous_hash":previous_hash,
                       "freeze_timestamp":source.get("freeze_timestamp",int(time.time())),"merkle_root":root(records),"start_ns":str(start_ns or start*10**9),"end_ns":str(end_ns or end*10**9)}
            if asset_mapping is not None:
                payload["asset_mapping"]=asset_mapping
                payload["asset_mapping_ref"]=store.put(canonical(asset_mapping))
            epoch = Epoch(id=epoch_id,number=number,mode=mode,status="frozen",start=start,end=end,payload=payload)
            db.add(epoch)
            db.flush()
            for offset in range(0,len(records),1000):
                db.execute(insert(EpochTransaction),[{"epoch_id":epoch_id,"record_key":record["public_record_identifier"],"position":i,"record":record} for i,record in enumerate(records[offset:offset+1000],offset)])
        elif epoch.payload["records"] != records or epoch.start != start or epoch.end != end:
            raise ValueError("Frozen epoch inputs cannot change")
        if mode=="live" and job.attempts>=3 and not epoch.payload.get("creative"):
            raise ValueError("Published creative-generation retry budget exhausted")
        job.status="running"; job.attempts+=1; job.updated_at=int(time.time()); job.error=None
        frozen = epoch.payload
    try:
        records = frozen["records"]
        asset_mapping=frozen.get("asset_mapping")
        if asset_mapping is not None and sha(canonical(asset_mapping)).hex()!=frozen["asset_mapping_ref"]["sha256"]:
            raise ValueError("Frozen network mapping hash mismatch")
        stats = statistics(records,start,end,asset_mapping)
        seed = master_seed(number,frozen["merkle_root"],frozen["block"]["hash"],frozen["beacon"]["randomness"],frozen["previous_hash"])
        if asset_mapping is not None:
            seed=mapped_seed(seed,asset_mapping)
        with factory() as db:
            persisted_direction = db.get(Epoch,epoch_id).payload.get("creative")
        if persisted_direction is None:
            direction, ai = await creative_direction(seed,stats,settings)
            curation={"theme":"celestial","source":"published_default","applied":False}
            if mode!="demo" and settings.near_auction_contract:
                expected_deadline=(selection["sunday_start"]+17*3600)*10**9
                choice=await NearRPC(settings.near_rpc_url).view(settings.near_auction_contract,"get_theme_for",{"deadline_ns":str(expected_deadline)})
                if choice.get("locked") and choice.get("token_id") and int(choice["deadline_ns"])==expected_deadline:
                    curation={**choice,"source":"locked_onchain_owner_choice","applied":True}
                    direction=apply_curatorial_theme(direction,choice["theme"])
            persisted_direction = {"direction":direction,"ai":ai,"curation":curation}
            with factory.begin() as db:
                epoch=db.get(Epoch,epoch_id)
                epoch.payload={**epoch.payload,"creative":persisted_direction}
        direction, ai = persisted_direction["direction"], persisted_direction["ai"]
        manifest=scene(seed,records,stats,direction,start,end,frozen["previous_hash"],number,asset_mapping)
        files=render(manifest)
        files["artwork-manifest.json"]=canonical(manifest)
        files["source-snapshot.json"]=canonical(records)
        if asset_mapping is not None:
            files["asset-networks.json"]=canonical(asset_mapping)
        files["merkle-proofs.json"]=canonical(proof_index(records))
        files["animation-manifest.json"]=canonical({"version":"motion-v1","seed":seed,"period_seconds":24,"motion":"fixed SVG layers; optional presentation rotation","canonical":"static PNG"})
        refs={name:store.put(data) for name,data in files.items()}
        provenance={"schema_version":"echo-provenance-v1","id":epoch_id,"epoch":number,"mode":mode,
            "data_classification":source["classification"],"interval":{"start":start,"end":end,"start_ns":frozen["start_ns"],"end_ns":frozen["end_ns"],"rule":"[start,end)","timestamp_field":"createdAtTimestamp"},
            "snapshot":refs["source-snapshot.json"],"merkle_root":frozen["merkle_root"],"transaction_count":len(records),
            "freeze_timestamp":frozen["freeze_timestamp"],"source":source,"block":frozen["block"],"beacon":frozen["beacon"],
            "selection":frozen["selection"],"master_seed":seed,"previous_artwork_hash":frozen["previous_hash"],
            "renderer_version":manifest["version"],"direction":direction,"ai":ai,"curation":persisted_direction.get("curation",{"source":"published_default"}),"files":refs,
            "trust":{"data_completeness":"provider-trusted; Merkle membership is not a completeness proof", "randomness":"offchain BLS verification; contract stores commitments", "storage":"S3 content-addressed immutable keys" if settings.storage_provider=="s3" else "local content-addressed store; not IPFS-pinned", "image":"static file hash authoritative; replay requires pinned renderer dependencies"}}
        if asset_mapping is not None:
            provenance["asset_mapping"]=refs["asset-networks.json"]
        provenance_ref=store.put(canonical(provenance))
        result={"id":epoch_id,"edition":f"ECHO-{number:06d}","number":number,"mode":mode,"title":direction["title"],
                "description":direction["description"],"composition":direction["composition"],"palette":direction["palette"],
                "image":refs["artwork.png"]["uri"],"svg":refs["artwork.svg"]["uri"],"thumbnail":refs["thumbnail.webp"]["uri"],
                "image_hash":refs["artwork.png"]["sha256"],"provenance":provenance_ref,"manifest":refs["artwork-manifest.json"],
                "seed":seed,"merkle_root":frozen["merkle_root"],"stats":stats,"start":start,"end":end,
                "ai_provider":ai["provider"],"block":frozen["block"],"nft":{"status":"not_minted","token_id":None,"transaction_hash":None},
                "auction":{"status":"not_created","highest_bid":None}}
        with factory.begin() as db:
            db.add(Artwork(id=epoch_id,epoch_id=epoch_id,image_hash=result["image_hash"],payload=result))
            db.get(Epoch,epoch_id).status="rendered"
            db.get(Job,key).status="succeeded"
            db.get(Job,key).updated_at=int(time.time())
        return result
    except Exception as exc:
        with factory.begin() as db:
            job=db.get(Job,key); job.status="failed"; job.error=type(exc).__name__; job.updated_at=int(time.time())
        raise

async def run_demo(factory, settings):
    import json
    fixture=json.loads((ROOT/"fixtures/sample-epoch/transactions.json").read_text())
    evidence=json.loads((ROOT/"fixtures/sample-epoch/evidence.json").read_text())
    return await run_epoch(factory,settings,number=1,mode="demo",raw=fixture["records"],start=fixture["start"],end=fixture["end"],
        block=evidence["block"],beacon=evidence["beacon"],selection=evidence["selection"],source=fixture["source"])
