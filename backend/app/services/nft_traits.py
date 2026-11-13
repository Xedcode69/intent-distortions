"""Immutable collectible attributes derived from hash-checked, frozen rendering inputs.

This projection never changes the original artwork/provenance. Financial rights
are queried separately; their changing state is never an artistic attribute.
"""
import base64
import json
import math
from .canonical_data import canonical, sha

SCHEMA = "echo-nft-traits-v1"
FAMILIES = {"orbital_network":"Orbital network", "fractal_branches":"Fractal branches",
    "crystalline":"Crystalline", "flow_field":"Flow field", "spiral_constellation":"Spiral constellation", "particle_nebula":"Particle nebula"}
CONTROL_NAMES = {"depth":"Branch depth", "arms":"Arm count", "facets":"Facet count", "steps":"Integration steps",
    "streams":"Stream count", "dust":"Dust count", "tilt":"Tilt (radians)", "growth_direction":"Growth direction (radians)"}

def _read(store, ref):
    data = store.get(ref["sha256"])
    if sha(data).hex() != ref["sha256"]:raise ValueError("Trait source hash mismatch")
    return json.loads(data)

def trait_bundle(store, artwork):
    p = _read(store, artwork["provenance"])
    manifest_ref = p["files"]["artwork-manifest.json"]
    if (manifest_ref != artwork["manifest"] or p["epoch"] != artwork["number"]
            or p["master_seed"] != artwork["seed"] or p["merkle_root"] != artwork["merkle_root"]
            or p["files"]["artwork.png"]["sha256"] != artwork["image_hash"]):
        raise ValueError("Trait source differs from artwork commitments")
    m = _read(store, manifest_ref)
    if m["version"] != p["renderer_version"] or m["family"] != p["direction"]["composition"]:
        raise ValueError("Trait scene/direction mismatch")
    features = None
    if m["version"] == "echo-renderer-4":
        ref = p["files"]["visual-features.json"]
        if m["visual_features_sha256"] != ref["sha256"]:raise ValueError("Trait feature commitment mismatch")
        features = _read(store, ref)
        if features["record_count"] != p["transaction_count"]:raise ValueError("Trait record count mismatch")
        networks = {node["network"] for node in features["nodes"] if node["outgoing"]>0 and node["network"]!="Unmapped"}
        route_count = features["route_count"]
    else:
        from .art_statistics import chain
        records = _read(store, p["snapshot"])
        if len(records) != p["transaction_count"]:raise ValueError("Trait record count mismatch")
        mapping = _read(store, p["asset_mapping"]) if "asset_mapping" in p else None
        networks = {chain(row["origin_asset"],mapping) for row in records}-{"Unmapped"}
        route_count = len({(chain(row["origin_asset"],mapping),chain(row["destination_asset"],mapping)) for row in records})
    attrs = []
    def add(name,value):
        if isinstance(value,bool) or not isinstance(value,(str,int,float)) or isinstance(value,float) and not math.isfinite(value):
            raise ValueError("Invalid NFT trait value")
        if len(name)>64 or isinstance(value,str) and len(value)>160:raise ValueError("NFT trait exceeds bounds")
        attrs.append({"trait_type":name,"value":value})
    add("Art family",FAMILIES[m["family"]])
    add("Global edition",p["epoch"])
    add("Renderer version",m["version"])
    add("Contributing records",p["transaction_count"])
    add("Recognized source networks",len(networks))
    add("Network routes",route_count)
    add("Symmetry",p["direction"]["symmetry"])
    add("Image width",m["width"]);add("Image height",m["height"])
    # Older renderers did not implement material/theme controls: do not invent
    # those traits from descriptive AI text in their historical provenance.
    style = m.get("controls",{}).get("style")
    if style:
        add("Material",style["material"]);add("Theme",style["theme"]);add("Complexity",style["complexity"])
        add("Background","Dark" if style["dark"] else "Light")
        palette = style["palette"]
        for name in ("perspective","light_intensity","texture_density"):
            if name in style:add(name.replace("_"," ").capitalize(),style[name])
        for name,value in sorted(m["controls"]["family"].items()):
            if name == "rotation_direction":value="Clockwise" if value==1 else "Counterclockwise"
            add(CONTROL_NAMES.get(name,name.replace("_"," ").capitalize()),value)
    else:
        palette = sorted({shape["color"] for shape in m["shapes"]})[:8]
    for i,color in enumerate(palette):add(f"Palette colour {i+1}",color)
    if features:
        add("Distinct assets",features["asset_count"])
        for name in ("burstiness","flow_imbalance","reciprocity","route_diversity"):
            add(name.replace("_"," ").capitalize(),features[name])
    if len(attrs)>64:raise ValueError("Too many NFT traits")
    document = {"schema":SCHEMA,"name":p["direction"]["title"],"description":p["direction"]["description"],"attributes":attrs,"source":{"provenance_sha256":artwork["provenance"]["sha256"],
        "manifest_sha256":manifest_ref["sha256"],"image_sha256":artwork["image_hash"],"seed":p["master_seed"],"merkle_root":p["merkle_root"]}}
    return {**document,"sha256":sha(canonical(document)).hex()}

def publish_traits(store, artwork):
    bundle = trait_bundle(store,artwork)
    document = {key:value for key,value in bundle.items() if key!="sha256"}
    ref = store.put(canonical(document))
    if ref["sha256"] != bundle["sha256"]:raise ValueError("Published NFT trait hash mismatch")
    return bundle,ref

def token_metadata(artwork,bundle,ref,media_uri=None,provenance_uri=None):
    if ref["sha256"] != bundle["sha256"]:raise ValueError("NFT trait reference mismatch")
    extra={"trait_schema":SCHEMA,"attributes":bundle["attributes"],"traits_reference":ref,"trait_source":bundle["source"]}
    return {"title":bundle["name"],"description":bundle["description"],"media":media_uri or artwork["image"],
        "media_hash":base64.b64encode(bytes.fromhex(artwork["image_hash"])).decode(),"copies":1,
        "reference":provenance_uri or artwork["provenance"]["uri"],
        "reference_hash":base64.b64encode(bytes.fromhex(artwork["provenance"]["sha256"])).decode(),"extra":canonical(extra).decode()}
