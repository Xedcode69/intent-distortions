import json
from .canonical_data import canonical, sha
from .merkle import root
from .art_seed import master_seed
from .art_renderer import render

def verify_artwork(store, artwork, rerender=False):
    p = json.loads(store.get(artwork["provenance"]["sha256"]))
    records = json.loads(store.get(p["snapshot"]["sha256"]))
    checks = {"provenance_content_hash": sha(canonical(p)).hex()==artwork["provenance"]["sha256"],
              "artwork_commitments":artwork["id"]==p["id"] and artwork["number"]==p["epoch"] and artwork["mode"]==p["mode"] and artwork["seed"]==p["master_seed"] and artwork["merkle_root"]==p["merkle_root"] and artwork["block"]["hash"]==p["block"]["hash"] and artwork["image_hash"]==p["files"]["artwork.png"]["sha256"],
              "snapshot_content_hash":sha(canonical(records)).hex()==p["snapshot"]["sha256"],
              "merkle_root": root(records)==p["merkle_root"],
              "record_count":len(records)==p["transaction_count"],
              "master_seed":master_seed(p["epoch"],root(records),p["block"]["hash"],p["beacon"]["randomness"],p["previous_artwork_hash"])==p["master_seed"],
              "image_hash":sha(store.get(p["files"]["artwork.png"]["sha256"])).hex()==artwork["image_hash"]}
    for name, ref in p["files"].items():
        checks[f"file:{name}"]=sha(store.get(ref["sha256"])).hex()==ref["sha256"]
    if rerender:
        manifest=json.loads(store.get(p["files"]["artwork-manifest.json"]["sha256"]))
        from .art_renderer import scene,scene_v1
        from .art_statistics import statistics
        generator={"echo-renderer-1":scene_v1,"echo-renderer-2":scene}.get(p["renderer_version"])
        stats=statistics(records,p["interval"]["start"],p["interval"]["end"])
        derived=generator(p["master_seed"],records,stats,p["direction"],p["interval"]["start"],p["interval"]["end"],p["previous_artwork_hash"],p["epoch"]) if generator else None
        checks["scene_derivation"]=derived is not None and canonical(derived)==canonical(manifest)
        checks["statistics_derivation"]=canonical(stats)==canonical(artwork["stats"])
        checks["render_replay"]=sha(render(manifest)["artwork.png"]).hex()==artwork["image_hash"]
    return {"valid":all(checks.values()),"checks":checks,"scope":"Content integrity and deterministic commitments; not source completeness or NFT ownership", "data_classification":p["data_classification"]}
