import json
from copy import deepcopy
import pytest
from app.services.nft_traits import trait_bundle,publish_traits,token_metadata
from app.services.storage import ContentStore
from app.services.canonical_data import canonical,sha

def saved(tmp_path,version="echo-renderer-4",family="crystalline"):
    store=ContentStore(tmp_path)
    put=lambda data:store.put(canonical(data))
    features={"record_count":3,"asset_count":4,"route_count":2,"nodes":[{"network":"NEAR","outgoing":1},{"network":"Ethereum","outgoing":1},{"network":"Unmapped","outgoing":1},{"network":"Solana","outgoing":0}],
        "burstiness":.2,"flow_imbalance":.3,"reciprocity":.4,"route_diversity":.5}
    feature_ref=put(features)
    m={"version":version,"family":family,"width":1440,"height":1440,"visual_features_sha256":feature_ref["sha256"],
        "shapes":[{"color":"#123456"}],"controls":{"family":{"facets":14,"subdivisions":5},
            "style":{"material":"glass","theme":"celestial","complexity":.8,"dark":True,"palette":["#ABCDEF","#123456"]}}}
    records=[{"origin_asset":"wrap.near","destination_asset":"eth-usdc"}]*3
    p={"epoch":1,"transaction_count":3,"master_seed":"01"*32,"merkle_root":"02"*32,"renderer_version":version,
        "direction":{"composition":family,"material":"descriptive AI material that must not become the trait","symmetry":6,"title":"Frozen title","description":"Frozen description"},
        "snapshot":put(records),"files":{"artwork.png":store.put(b"image"),"artwork-manifest.json":put(m),"visual-features.json":feature_ref}}
    art={"number":1,"title":"Mutable label","description":"Mutable text","seed":p["master_seed"],"merkle_root":p["merkle_root"],
        "manifest":p["files"]["artwork-manifest.json"],"image_hash":p["files"]["artwork.png"]["sha256"],"image":"https://art.example/image","provenance":put(p),"stats":{"unique_chains":999}}
    return store,art,p,m

def values(bundle):return {a["trait_type"]:a["value"] for a in bundle["attributes"]}

def test_traits_use_resolved_scene_and_committed_features_not_mutable_labels(tmp_path):
    store,art,_,_=saved(tmp_path);a=trait_bundle(store,art);v=values(a)
    assert v["Art family"]=="Crystalline" and v["Material"]=="glass" and v["Theme"]=="celestial"
    assert v["Complexity"]==.8 and v["Facet count"]==14 and v["Palette colour 1"]=="#ABCDEF"
    assert v["Contributing records"]==3 and v["Recognized source networks"]==2
    assert a["name"]=="Frozen title" and a["description"]=="Frozen description"
    changed={**art,"stats":{"unique_chains":1},"title":"Changed","palette":["#000000"],"composition":"orbital_network"}
    assert trait_bundle(store,changed)==a
    assert not any(word in v for word in ("Balance","Owner","Raffle eligibility","Treasury"))

def test_hash_linked_trait_document_and_mint_metadata_round_trip(tmp_path):
    store,art,_,_=saved(tmp_path);bundle,ref=publish_traits(store,art)
    assert sha(store.get(ref["sha256"])).hex()==bundle["sha256"]
    m=token_metadata(art,bundle,ref);extra=json.loads(m["extra"])
    assert extra["attributes"]==bundle["attributes"] and extra["traits_reference"]==ref
    assert m["reference"]==art["provenance"]["uri"] and m["title"]=="Frozen title"
    assert trait_bundle(store,art)==bundle

def test_trait_sources_cannot_be_swapped_or_tampered(tmp_path):
    store,art,_,_=saved(tmp_path)
    with pytest.raises(ValueError,match="commitments"):trait_bundle(store,{**art,"seed":"ff"*32})
    path=store.directory/art["manifest"]["sha256"];path.write_bytes(b"changed")
    with pytest.raises(ValueError,match="hash"):trait_bundle(store,art)

def test_legacy_renderer_does_not_claim_unimplemented_material_controls(tmp_path):
    store,art,p,m=saved(tmp_path,"echo-renderer-2")
    del m["controls"];p["files"]["artwork-manifest.json"]=store.put(canonical(m));art["manifest"]=p["files"]["artwork-manifest.json"];art["provenance"]=store.put(canonical(p))
    v=values(trait_bundle(store,art));assert "Material" not in v and "Theme" not in v
    assert v["Recognized source networks"]==1 and v["Palette colour 1"]=="#123456"

@pytest.mark.parametrize("family",["orbital_network","fractal_branches","crystalline","flow_field","spiral_constellation","particle_nebula"])
def test_trait_projection_is_deterministic_for_each_family(tmp_path,family):
    store,art,_,_=saved(tmp_path,family=family)
    a=trait_bundle(store,art);assert a==trait_bundle(store,deepcopy(art));assert len(a["attributes"])<61
