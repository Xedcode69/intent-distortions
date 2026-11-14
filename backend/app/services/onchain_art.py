"""IDART1: frozen, bounded vector display lists. Never calls AI or changes an epoch.

Coordinates are integer thousandths. Shapes preserve the accepted scene's draw
order; the new format has its own canonical SVG, distinct from the source PNG.
"""
import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .canonical_data import canonical
from .provenance import verify_artwork

FORMAT = "intent-distortions-onchain-v1"
MAGIC = b"IDART1"
MAX_BYTES = 262144
MAX_SHAPES = 8192
KINDS = ("dot", "line", "curve", "polygon")


def quantize(value, scale=1000, maximum=16777215):
    number = Decimal(str(value)) * scale
    if not number.is_finite():
        raise ValueError("Non-finite onchain coordinate")
    result = int(number.to_integral_value(rounding=ROUND_HALF_UP))
    if not 0 <= result <= maximum:
        raise ValueError("Onchain number exceeds bounds")
    return result


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Literal RGB colour required")
    return bytes.fromhex(value[1:])


def motion_controls(features, family, seed):
    from .family_selection import FAMILIES
    def metric(name):
        return quantize(features[name], 1000, 1000)
    burst, imbalance = metric("burstiness"), metric("flow_imbalance")
    diversity, reciprocity = metric("route_diversity"), metric("reciprocity")
    inequality = metric("size_inequality")
    variant = (int(seed[:8], 16) + diversity + reciprocity + burst) % 3
    return {"version":"frozen-data-motion-v1", "profile":FAMILIES.index(family), "variant":variant,
            "strength":min(1000, 200 + (burst * 3 + inequality) // 5),
            "direction":0 if imbalance > 250 else 1,
            "route_period_ms":max(1000, 9000 - diversity * 4 - imbalance * 2),
            "burstiness":burst,"flow_imbalance":imbalance,"route_diversity":diversity,
            "reciprocity":reciprocity,"size_inequality":inequality,
            "communities":features["community_count"],
            "meaning":"Fixed artistic encodings of aggregate activity; not settlement speed"}


def pack_scene(scene, motion):
    if scene.get("version") != "echo-renderer-4":
        raise ValueError("Onchain prototype requires a verified renderer-4 scene")
    shapes = scene["shapes"]
    if not 1 <= len(shapes) <= MAX_SHAPES:
        raise ValueError("Onchain shape budget exceeded")
    width, height = scene["width"], scene["height"]
    if type(width) is not int or type(height) is not int or not 64 <= width <= 2048 or not 64 <= height <= 2048:
        raise ValueError("Invalid onchain canvas")
    animation = scene["animation"]
    period = quantize(animation["period_seconds"], maximum=60000)
    pulse = quantize(animation["pulse_hz"], maximum=1000)
    if period < 1000 or pulse < 80 or len(animation["activity_profile"]) != 48:
        raise ValueError("Invalid onchain timeline")
    data = bytearray(MAGIC)
    def integer(n, size):
        data.extend(n.to_bytes(size, "big"))
    integer(width, 2); integer(height, 2)
    data.extend(color(scene["background_style"]["top"]))
    data.extend(color(scene["background_style"]["bottom"]))
    integer(len(shapes), 2); integer(period, 2); integer(pulse, 2)
    data.extend(quantize(v, 255, 255) for v in animation["activity_profile"])
    integer(motion["profile"] * 3 + motion["variant"], 1)
    integer(motion["strength"], 2); integer(motion["direction"], 1)
    integer(motion["route_period_ms"], 2)
    vertices = 0
    for index, shape in enumerate(shapes):
        kind = KINDS.index(shape["kind"])
        integer(kind, 1); data.extend(color(shape["color"]))
        alpha = shape["alpha"]
        if type(alpha) is not int or not 0 <= alpha <= 255:
            raise ValueError("Invalid onchain opacity")
        integer(alpha, 1)
        stroke = shape.get("stroke")
        flags = (1 if stroke else 0) | (2 if shape.get("glow") else 0)
        if shape["layer"] == "particles" and index % 7 == 0:
            flags |= 4
        if shape["layer"] == "routes" and kind in (1, 2):
            flags |= 8
        if scene.get("family") == "fractal_branches" and shape["layer"] == "geometry" and kind in (1, 2):
            flags |= 16
        integer(flags, 1)
        integer(quantize(shape.get("time", 0), 65535, 65535), 2)
        if flags & 8:
            integer(quantize(shape.get("weight", 0), 255, 255), 1)
        if stroke:
            data.extend(color(stroke))
        size = shape["radius"] if kind == 0 else shape.get("width", 1)
        integer(quantize(size, maximum=100000), 3)
        points = [shape["center"]] if kind == 0 else shape["points"]
        if not 1 <= len(points) <= 512 or kind == 1 and len(points) < 2 or kind == 2 and len(points) != 4 or kind == 3 and len(points) < 3:
            raise ValueError("Invalid onchain path")
        if kind:
            integer(len(points), 2)
        vertices += len(points)
        if vertices > 32768:
            raise ValueError("Onchain vertex budget exceeded")
        for x, y in points:
            integer(quantize(x, maximum=width * 1000), 3)
            integer(quantize(y, maximum=height * 1000), 3)
    if len(data) > MAX_BYTES:
        raise ValueError("Onchain recipe budget exceeded")
    return bytes(data)


def prepare_prototype(store, artwork, output):
    """Verify saved data first; export only public, allowlisted artistic fields."""
    if not verify_artwork(store, artwork, rerender=True)["valid"]:
        raise ValueError("Source artwork failed full provenance replay")
    provenance = json.loads(store.get(artwork["provenance"]["sha256"]))
    manifest = json.loads(store.get(artwork["manifest"]["sha256"]))
    ai = provenance["ai"]
    if ai.get("provider") != "near_ai_cloud" or ai.get("policy") != "first-valid-v1":
        raise ValueError("Prototype requires a persisted NEAR AI artistic direction")
    from .family_selection import select_family
    selection = select_family(artwork["seed"])
    if selection != provenance["family_selection"] or selection["family"] != manifest["family"]:
        raise ValueError("Frozen family selection mismatch")
    features = json.loads(store.get(provenance["files"]["visual-features.json"]["sha256"]))
    motion = motion_controls(features, manifest["family"], artwork["seed"])
    recipe = pack_scene(manifest, motion)
    from .nft_traits import trait_bundle
    traits = trait_bundle(store, artwork)
    metadata = {
        "title": artwork["title"], "description": artwork["description"],
        "family": manifest["family"], "direction": canonical(provenance["direction"]).decode(),
        "ai_model": ai["model"], "seed": artwork["seed"], "merkle_root": artwork["merkle_root"],
        "source_provenance": artwork["provenance"]["sha256"],
        "source_manifest": artwork["manifest"]["sha256"], "source_image": artwork["image_hash"],
        "source_edition": artwork["edition"], "source_start": str(artwork["start"]), "source_end": str(artwork["end"]),
        "record_count": provenance["transaction_count"],
        "traits": canonical(traits["attributes"]).decode(),
        "motion":canonical(motion).decode(), "prototype": True,
    }
    # Fail closed on accidental URL/secret additions; raw records and AI prompts
    # are deliberately absent. Typed contract metadata rejects unknown fields too.
    allowed = {"title","description","family","direction","ai_model","seed","merkle_root","source_provenance",
               "source_manifest","source_image","source_edition","source_start","source_end","record_count","traits","motion","prototype"}
    if set(metadata) != allowed or len(canonical(metadata)) > 10000:
        raise ValueError("Prototype public metadata exceeds allowlist/budget")
    document = {"format": FORMAT, "token_id": "ONCHAIN-PROTOTYPE-000001", "metadata": metadata,
                "recipe_sha256": hashlib.sha256(recipe).hexdigest(), "recipe_bytes": len(recipe),
                "source_svg_bytes": len(store.get(provenance["files"]["artwork.svg"]["sha256"])),
                "shape_count": len(manifest["shapes"]),
                "notice": "Separate onchain-format prototype derived from saved historical data; no primary auction or reward allocation."}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, content in {"recipe.bin":recipe, "prototype.json":canonical(document)}.items():
        target = output / name
        if target.exists() and target.read_bytes() != content:
            raise ValueError("Prepared prototype cannot be overwritten with different bytes")
        target.write_bytes(content)
    return document
