import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.config import settings
from app.database import init_db, Artwork
from app.services.provenance import verify_artwork
from app.services.storage import content_store

parser=argparse.ArgumentParser()
parser.add_argument("id",nargs="?",default="demo-000001")
args=parser.parse_args()
if args.id.startswith("demo-"):
    from fixture_profile import fixture_settings
    settings=fixture_settings()
with init_db(settings.database_url)() as db:
    row=db.get(Artwork,args.id)
    if not row: raise SystemExit("Edition not found: run scripts/run_demo_epoch.py first")
    result=verify_artwork(content_store(settings),row.payload,True)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["valid"] else 1)
