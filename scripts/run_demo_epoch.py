import asyncio
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.config import settings
from app.database import init_db
from app.services.epoch_manager import run_demo
from fixture_profile import fixture_settings

async def main():
    config=fixture_settings()
    result=await run_demo(init_db(config.database_url),config)
    print(json.dumps({k:result[k] for k in ("id","title","image_hash","merkle_root","ai_provider","nft","auction")},indent=2))

if __name__=="__main__": asyncio.run(main())
