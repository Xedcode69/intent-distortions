import json
from .canonical_data import canonical, sha
from .merkle import root
from .art_seed import master_seed
from .art_renderer import render

def verify_artwork(store, artwork, rerender=False):
    p = json.loads(store.get(artwork["provenance"]["sha256"]))
    records = json.loads(store.get(p["snapshot"]["sha256"]))
    mapping=None
    network_renderer=p["renderer_version"] in ("echo-renderer-3","echo-renderer-4")
    mapping_valid=not network_renderer and "asset_mapping" not in p
    if network_renderer and p.get("asset_mapping")==p["files"].get("asset-networks.json") and p.get("asset_mapping"):
        from .asset_networks import validate_asset_mapping, mapping_summary
        mapping=json.loads(store.get(p["asset_mapping"]["sha256"]))
        validate_asset_mapping(mapping,records)
        mapping_valid=(sha(canonical(mapping)).hex()==p["asset_mapping"]["sha256"]
                       and artwork["stats"].get("network_mapping")==mapping_summary(mapping,records))
    expected_seed=master_seed(p["epoch"],root(records),p["block"]["hash"],p["beacon"]["randomness"],p["previous_artwork_hash"])
    if network_renderer and mapping is not None:
        from .asset_networks import mapped_seed
        expected_seed=mapped_seed(expected_seed,mapping)
    checks = {"provenance_content_hash": sha(canonical(p)).hex()==artwork["provenance"]["sha256"],
              "artwork_commitments":artwork["id"]==p["id"] and artwork["number"]==p["epoch"] and artwork["mode"]==p["mode"] and artwork["seed"]==p["master_seed"] and artwork["merkle_root"]==p["merkle_root"] and artwork["block"]["hash"]==p["block"]["hash"] and artwork["image_hash"]==p["files"]["artwork.png"]["sha256"],
              "snapshot_content_hash":sha(canonical(records)).hex()==p["snapshot"]["sha256"],
              "merkle_root": root(records)==p["merkle_root"],
              "record_count":len(records)==p["transaction_count"],
              "master_seed":expected_seed==p["master_seed"],
              "image_hash":sha(store.get(p["files"]["artwork.png"]["sha256"])).hex()==artwork["image_hash"]}
    if network_renderer or "asset_mapping" in p:
        checks["frozen_asset_networks"]=mapping_valid
    if p["renderer_version"]=="echo-renderer-4":
        from .family_selection import select_family
        selection=select_family(expected_seed)
        checks["verifiable_family_selection"]=p.get("family_selection")==selection and p["direction"]["composition"]==selection["family"]
        features_ref=p.get("visual_features")
        checks["frozen_visual_features"]=(features_ref is not None and features_ref==p["files"].get("visual-features.json")
            and json.loads(store.get(features_ref["sha256"]))==artwork["stats"].get("visual_features"))
    for name, ref in p["files"].items():
        checks[f"file:{name}"]=sha(store.get(ref["sha256"])).hex()==ref["sha256"]
    if rerender:
        manifest=json.loads(store.get(p["files"]["artwork-manifest.json"]["sha256"]))
        from .art_renderer import scene,scene_v1
        from .art_statistics import statistics
        from .expressive_renderer import scene_v4
        generator={"echo-renderer-1":scene_v1,"echo-renderer-2":scene,"echo-renderer-3":scene,"echo-renderer-4":scene_v4}.get(p["renderer_version"])
        if p["renderer_version"]=="echo-renderer-4":
            from .visual_features import expressive_statistics
            stats=expressive_statistics(records,p["interval"]["start"],p["interval"]["end"],mapping)
        else:
            stats=statistics(records,p["interval"]["start"],p["interval"]["end"],mapping)
        kwargs={"asset_mapping":mapping} if network_renderer else {}
        derived=generator(p["master_seed"],records,stats,p["direction"],p["interval"]["start"],p["interval"]["end"],p["previous_artwork_hash"],p["epoch"],**kwargs) if generator and (not network_renderer or mapping is not None) else None
        checks["scene_derivation"]=derived is not None and canonical(derived)==canonical(manifest)
        checks["statistics_derivation"]=canonical(stats)==canonical(artwork["stats"])
        checks["render_replay"]=sha(render(manifest)["artwork.png"]).hex()==artwork["image_hash"]
    return {"valid":all(checks.values()),"checks":checks,"scope":"Content integrity and deterministic commitments; not source completeness or NFT ownership", "data_classification":p["data_classification"]}
