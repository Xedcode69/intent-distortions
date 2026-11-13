"""Build a public educational sample with no database, API keys, or chain writes."""
import json
from pathlib import Path
import base58
from app.services.canonical_data import canonical,sha,snapshot
from app.services.merkle import root
from app.services.randomness import select_timestamp
from app.services.art_seed import master_seed,GENESIS_HASH
from app.services.art_statistics import statistics
from app.services.near_ai import fallback
from app.services.art_renderer import scene,render

ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/"demo/assets";directory.mkdir(parents=True,exist_ok=True)
sunday=1794096000;start=1793577600
randomness=sha(b"NEAR_ECHOES_EXPLAINER_SYNTHETIC_RANDOMNESS_V1").hex()
target=select_timestamp(1,randomness,sunday)
block_hash=base58.b58encode(sha(b"NEAR_ECHOES_EXPLAINER_SYNTHETIC_BLOCK_V1")).decode()
fixture=json.loads((ROOT/"fixtures/sample-epoch/transactions.json").read_text())
raw=[{**r,"createdAtTimestamp":start+((target-start)*(i+1))//37,"depositAddress":f"EXPLAINER-SYNTHETIC-{i}"} for i,r in enumerate(fixture["records"])]
records=snapshot(raw,start,target+1,end_ns=target*10**9+200_000_000)
merkle=root(records);seed=master_seed(1,merkle,block_hash,randomness,GENESIS_HASH)
stats=statistics(records,start,target+1);direction=fallback(seed,stats).model_dump()
manifest=scene(seed,records,stats,direction,start,target+1,GENESIS_HASH,1)
files=render(manifest)
for name,data in files.items():(directory/name).write_bytes(data)
(directory/"scene.json").write_bytes(canonical(manifest))
example={"classification":"synthetic_educational_sample","label":"EXPLAINER-001","epoch":1,"title":direction["title"],
    "description":"All swap-shaped records, block evidence, randomness and auction examples are synthetic. No live transaction is represented.",
    "sunday_start":sunday,"interval_start":start,"interval_end_ns":str(target*10**9+200_000_000),
    "selected_timestamp":target,"block":{"height":42,"hash":block_hash,"timestamp_ns":str(target*10**9+200_000_000),"verified":False},
    "randomness":randomness,"randomness_verified":False,"previous_image_hash":GENESIS_HASH,"records":records,"statistics":stats,
    "merkle_root":merkle,"master_seed":seed,"snapshot_hash":sha(canonical(records)).hex(),"image_hash":sha(files["artwork.png"]).hex(),"composition":direction["composition"]}
(directory/"example.json").write_bytes(canonical(example))
print(f"Built isolated educational demo: {len(records)} synthetic records, {stats['particle_count']} particles; no database touched")
