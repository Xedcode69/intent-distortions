"""Public collection presentation; original source commitments remain unchanged."""
import copy,json
from pathlib import Path

def genesis(settings):
    if settings.execution_mode!="live" or not settings.onchain_art_contract:return None
    value=json.loads((Path(__file__).resolve().parents[3]/"fixtures/collection/genesis.json").read_text())
    if value["nft"]["contract"]!=settings.onchain_art_contract or value["edition"]!=settings.onchain_art_token_id:
        raise ValueError("Genesis account must match the preserved edition")
    return value

def present(art):
    if not art.get("onchain_art"):return art
    result=copy.deepcopy(art);bundle=result.pop("onchain_art")
    base=f"/api/v1/onchain/editions/{art['edition']}"
    result.update(image=base+"/static.svg",svg=base+"/static.svg",thumbnail=base+"/static.svg",
        image_hash=bundle["static"]["sha256"],source_image_hash=art["image_hash"],
        source_provenance=art["provenance"],provenance={"uri":base+"/provenance.json","sha256":bundle["provenance"]["sha256"]},
        onchain_art={"format":bundle["format"],"static_sha256":bundle["static"]["sha256"],
            "animated_sha256":bundle["animated"]["sha256"],"recipe_sha256":bundle["recipe"]["sha256"],
            "animated_url":base+"/animated.svg","sealed":art["nft"]["status"]=="minted"})
    # A draft's source preview is not the final onchain media.
    if art["nft"]["status"]!="minted":return art
    return result
