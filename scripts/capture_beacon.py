"""Capture a fixed historical Sunday beacon with local BLS verification."""
import asyncio
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.services.randomness import fetch_beacon,select_timestamp
from app.services.near_rpc import NearRPC
from app.config import settings

async def main():
    sunday=1794096000  # 2026-11-08 00:00:00 UTC; predetermined demo schedule
    beacon=await fetch_beacon(sunday+18*3600)
    target=select_timestamp(1,beacon["randomness"],sunday)
    directory=ROOT/"fixtures/sample-epoch"
    (directory/"verified-beacon.json").write_text(json.dumps(beacon,indent=2)+"\n")
    print(f"BLS verified round {beacon['round']}; selected timestamp {target}")
    block=await NearRPC(settings.near_mainnet_rpc_url).first_block_at(target)
    evidence={"block":block,"beacon":beacon,"selection":{"algorithm":"selection-v1","sunday_start":sunday,"selected_timestamp":target,"verified":True}}
    # Separate capture file: frozen demo evidence is never overwritten.
    (directory/"captured-evidence.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(f"Verified historical block {block['height']}; saved captured-evidence.json")

if __name__=="__main__": asyncio.run(main())
