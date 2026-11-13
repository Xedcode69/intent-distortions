"""Replay an authenticated local capture with independently checked beacon/block evidence."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.config import settings
from app.database import init_db,Artwork,Epoch
from app.services.canonical_data import snapshot,canonical,sha
from app.services.epoch_manager import run_epoch
from app.services.art_seed import GENESIS_HASH

async def main():
    p=argparse.ArgumentParser();p.add_argument("--capture",type=Path,required=True,help="data/captures/<hash>.source.json")
    p.add_argument("--evidence",type=Path,required=True);p.add_argument("--epoch",type=int,default=1);a=p.parse_args()
    if settings.execution_mode!="historical_replay":raise SystemExit("Set EXECUTION_MODE=historical_replay; demo/live state cannot be replayed here")
    source=json.loads(a.capture.read_text());digest=source["sha256"]
    if not source["complete"] or source["classification"]!="authenticated_explorer_capture":raise SystemExit("Complete authenticated capture required")
    raw=json.loads(a.capture.with_name(f"{digest}.raw.json").read_text())
    normalized=snapshot(raw,source["start"],source["end"])
    if sha(canonical(normalized)).hex()!=digest:raise SystemExit("Capture commitment mismatch")
    evidence=json.loads(a.evidence.read_text());block=evidence["block"]
    end=(int(block["timestamp_ns"])+10**9-1)//10**9
    if source["end"]<end:raise SystemExit("Capture does not cover selected block cutoff")
    factory=init_db();previous=GENESIS_HASH;start=source["start"];start_ns=start*10**9
    if a.epoch>1:
        with factory() as db:
            prev=db.get(Artwork,f"historical_replay-{a.epoch-1:06d}")
            if not prev:raise SystemExit("Previous edition required for consecutive checkpoints")
            epoch=db.get(Epoch,prev.epoch_id);start=epoch.end;start_ns=int(epoch.payload["end_ns"]);previous=prev.image_hash
    if source["start"]>start:raise SystemExit("Capture is missing the start checkpoint")
    result=await run_epoch(factory,settings,number=a.epoch,mode="historical_replay",raw=raw,start=start,end=end,
        start_ns=start_ns,block=block,beacon=evidence["beacon"],selection=evidence["selection"],
        source={**source,"reconciled":True,"freeze_rule":"historical replay of status observed at capture; not a production as-of status assertion"},previous_hash=previous)
    print(json.dumps({"id":result["id"],"image_hash":result["image_hash"],"source":"authenticated historical capture"},indent=2))

if __name__=="__main__":asyncio.run(main())
