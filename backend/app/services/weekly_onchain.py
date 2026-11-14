"""Frozen IDART1 publication. Public media and provenance are recovered from NEAR."""
import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from .canonical_data import canonical
from .onchain_art import pack_scene,motion_controls
from .nft_traits import trait_bundle

FORMAT="intent-distortions-weekly-onchain-v1"
def sha(data):return hashlib.sha256(data).hexdigest()

def prepare(store,artwork,account,renderer):
    old=artwork.get("onchain_art")
    if old:
        for name in ("recipe","static","animated","provenance"):
            store.get(old[name]["sha256"])
        if old["contract"]!=account:raise ValueError("Frozen collection binding changed")
        return old
    p=json.loads(store.get(artwork["provenance"]["sha256"]))
    if p["ai"].get("provider")!="near_ai_cloud" or p["ai"].get("policy")!="first-valid-v1":
        raise ValueError("A persisted NEAR AI direction is required")
    scene=json.loads(store.get(artwork["manifest"]["sha256"]))
    features=json.loads(store.get(p["files"]["visual-features.json"]["sha256"]))
    motion=motion_controls(features,scene["family"],artwork["seed"])
    recipe=pack_scene(scene,motion)
    binary=Path(renderer)
    if not binary.is_file():raise ValueError("Build the pinned onchain SVG renderer first")
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory);(path/"recipe.bin").write_bytes(recipe)
        subprocess.run([str(binary.resolve()),str(path/"recipe.bin"),artwork["title"],str(path)],
            check=True,capture_output=True,timeout=30)
        static=(path/"static.svg").read_bytes();animated=(path/"animated.svg").read_bytes()
    import xml.etree.ElementTree as ET
    for svg in (static,animated):
        if len(svg)>2_000_000:raise ValueError("Onchain SVG exceeds budget")
        ET.fromstring(svg)
    traits=trait_bundle(store,artwork)
    public={"format":FORMAT,"source_provenance_sha256":artwork["provenance"]["sha256"],
        "seed":artwork["seed"],"merkle_root":artwork["merkle_root"],"source_image_sha256":artwork["image_hash"],
        "source_start":artwork["start"],"source_end":artwork["end"],"records":p["transaction_count"],
        "recipe_sha256":sha(recipe),"static_sha256":sha(static),"animated_sha256":sha(animated),
        "direction":p["direction"],"ai":{key:p["ai"][key] for key in ("provider","policy","model")},
        "block":artwork["block"],"motion":motion,"attributes":traits["attributes"]}
    proof=canonical(public)
    media=f"near://{account}/{artwork['edition']}/static.svg"
    metadata={"title":artwork["title"],"description":artwork["description"],"media":media,
        "media_hash":base64.b64encode(bytes.fromhex(sha(static))).decode(),"copies":1,
        "reference":"data:application/json;base64,"+base64.b64encode(proof).decode(),
        "reference_hash":base64.b64encode(bytes.fromhex(sha(proof))).decode(),
        "extra":canonical({"format":FORMAT,"attributes":traits["attributes"],"recipe_sha256":sha(recipe),
            "static_sha256":sha(static),"animated_sha256":sha(animated),"animation_method":"get_animated_svg"}).decode()}
    # Rust serializes all optional NEP-177 fields, including explicit nulls.
    metadata={key:metadata.get(key) for key in ("title","description","media","media_hash","copies","issued_at","expires_at","starts_at","updated_at","extra","reference","reference_hash")}
    commitment={"epoch":artwork["number"],"image_hash":sha(static),"provenance_hash":sha(proof),
        "merkle_root":artwork["merkle_root"],"seed":artwork["seed"],"block_hash":artwork["block"]["hash"]}
    return {"format":FORMAT,"contract":account,"recipe":store.put(recipe),"static":store.put(static),
        "animated":store.put(animated),"provenance":store.put(proof),"recipe_bytes":len(recipe),
        "metadata":metadata,"metadata_sha256":sha(canonical(metadata)),"commitment":commitment}

async def publish_views(settings,artwork,bundle,store,writer,rpc,release_ns):
    contract=settings.near_nft_contract;token=artwork["edition"]
    state=await rpc.view(contract,"get_onchain_art",{"token_id":token})
    if state is None:
        await writer.submit(f"{artwork['id']}:art:begin",contract,"begin_onchain_art",{
            "release_ns":str(release_ns),"metadata":bundle["metadata"],"commitment":bundle["commitment"],
            "recipe_sha256":bundle["recipe"]["sha256"],"recipe_bytes":bundle["recipe_bytes"],
            "static_sha256":bundle["static"]["sha256"],"animated_sha256":bundle["animated"]["sha256"]},
            str((bundle["recipe_bytes"]+32000)*10**19))
        state=await rpc.view(contract,"get_onchain_art",{"token_id":token})
    def matches(s):
        return s and s["commitment"]==bundle["commitment"] and s["metadata_sha256"]==bundle["metadata_sha256"] \
            and s["recipe_bytes"]==bundle["recipe_bytes"] and all(s[k+"_sha256"]==bundle[k]["sha256"] for k in ("recipe","static","animated"))
    if not matches(state):raise ValueError("Onchain draft differs from frozen artwork")
    recipe=store.get(bundle["recipe"]["sha256"]);offset=state["uploaded_bytes"]
    if type(offset) is not int or not 0<=offset<=len(recipe):raise ValueError("Invalid uploaded offset")
    # Check every committed prefix byte before resuming; never replace old data.
    for start in range(0,offset,16384):
        saved=base64.b64decode(await rpc.view(contract,"get_recipe_chunk",{"token_id":token,"offset":start}),validate=True)
        if saved!=recipe[start:min(start+16384,offset)]:raise ValueError("Onchain upload prefix differs")
    while offset<len(recipe):
        data=recipe[offset:offset+16384]
        await writer.submit(f"{artwork['id']}:art:append:{offset}",contract,"append_onchain_recipe",{
            "token_id":token,"offset":offset,"data":base64.b64encode(data).decode()})
        offset+=len(data)
    for kind,animated in (("static",False),("animated",True)):
        if not state[kind+"_verified"]:
            await writer.submit(f"{artwork['id']}:art:verify:{kind}",contract,"verify_onchain_view",{"token_id":token,"animated":animated})
    if not state["sealed"]:
        await writer.submit(f"{artwork['id']}:mint",contract,"mint_onchain_art",{"token_id":token},str(10**24))
    final=await rpc.view(contract,"get_onchain_art",{"token_id":token})
    if not matches(final) or not final["sealed"]:raise ValueError("Onchain mint not sealed")
    return bundle["commitment"]

def resolve_media(token,account):
    metadata=token.get("metadata") or {}
    if metadata.get("media")==f"near://{account}/{token['token_id']}/static.svg":
        token={**token,"metadata":{**metadata,"media":f"/api/v1/onchain/editions/{token['token_id']}/static.svg"}}
    return token
