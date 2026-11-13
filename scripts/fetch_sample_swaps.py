"""Authenticated historical capture. Raw private data stays under ignored data/."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.config import settings
from app.services.intents_collector import Collector
from app.services.canonical_data import snapshot,canonical,sha

async def main():
    p=argparse.ArgumentParser(); p.add_argument("--start",type=int,required=True); p.add_argument("--end",type=int,required=True); a=p.parse_args()
    records,evidence=await Collector(settings.near_intents_explorer_url,settings.near_intents_partner_jwt).collect(a.start,a.end)
    clean=snapshot(records,a.start,a.end)
    folder=settings.data_dir/"captures";folder.mkdir(parents=True,exist_ok=True)
    digest=sha(canonical(clean)).hex()
    (folder/f"{digest}.raw.json").write_text(json.dumps(records))
    (folder/f"{digest}.json").write_bytes(canonical(clean))
    (folder/f"{digest}.source.json").write_text(json.dumps({**evidence,"classification":"authenticated_explorer_capture","start":a.start,"end":a.end,"sha256":digest},indent=2))
    print(f"Captured {len(clean)} successful records; canonical SHA-256 {digest}. Raw file is private and ignored by Git.")

if __name__=="__main__": asyncio.run(main())
