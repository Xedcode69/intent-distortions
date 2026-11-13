"""Export a frozen edition into a portable directory without changing its bytes."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.config import settings
from app.database import init_db,Artwork
from app.services.storage import content_store
from app.services.nft_traits import trait_bundle
from app.services.canonical_data import canonical

edition=sys.argv[1] if len(sys.argv)>1 else "demo-000001"
with init_db()() as db:
    row=db.get(Artwork,edition)
    if not row:raise SystemExit("Unknown artwork")
    store=content_store(settings)
    provenance=store.get(row.payload["provenance"]["sha256"])
    p=json.loads(provenance)
    directory=settings.data_dir/"exports"/edition;directory.mkdir(parents=True,exist_ok=True)
    for name,reference in p["files"].items():
        (directory/name).write_bytes(store.get(reference["sha256"]))
    (directory/"provenance.json").write_bytes(provenance)
    traits=trait_bundle(store,row.payload)
    (directory/"nft-traits.json").write_bytes(canonical({k:v for k,v in traits.items() if k!="sha256"}))
    print(f"Exported immutable edition to {directory}")
