"""Export one new onchain-format study without altering its saved source edition."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Reuse the isolated workflow's ambient-credential boundary.
from scripts import testnet_rehearsal as cli
from app.services import testnet_rehearsal as lab
from app.services.onchain_art import prepare_prototype

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--source',default='historical_replay-000001')
    parser.add_argument('--output',type=Path,default=ROOT/'data/onchain-prototypes/genesis-v1')
    args=parser.parse_args()
    if Path(sys.prefix).resolve()!=(ROOT/'.venv').resolve():raise ValueError('Use uv run --locked from the repository root')
    config=lab.load_settings(args.workspace)
    factory=lab.init_db(config.database_url,create_schema=False)
    with factory() as db:
        row=db.get(lab.Artwork,args.source)
        if row is None:raise ValueError('Saved source artwork not found')
        artwork=row.payload
    before=lab.canonical(artwork)
    result=prepare_prototype(lab.ContentStore(config.data_dir/'content'),artwork,args.output)
    with factory() as db:
        assert lab.canonical(db.get(lab.Artwork,args.source).payload)==before
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
