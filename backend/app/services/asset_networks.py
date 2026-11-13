"""Exact registry asset IDs, frozen with each edition; never infer from a ticker."""
import re
import time
import httpx
from .canonical_data import canonical, sha

REGISTRY_URL = "https://1click.chaindefuser.com/v0/tokens"
SCHEMA = "echo-asset-networks-v1"
POLICY = "exact-registry-asset-id-v1"
LABELS = {"near":"NEAR", "eth":"Ethereum", "sol":"Solana", "btc":"Bitcoin",
          "base":"Base", "arb":"Arbitrum", "bsc":"BNB Chain", "tron":"TRON",
          "op":"Optimism", "pol":"Polygon", "avax":"Avalanche", "gnosis":"Gnosis",
          "bera":"Berachain", "sui":"Sui", "aptos":"Aptos", "ton":"TON",
          "xrp":"XRP", "zec":"Zcash", "doge":"Dogecoin", "ltc":"Litecoin",
          "bch":"Bitcoin Cash", "stellar":"Stellar", "cardano":"Cardano",
          "dash":"Dash", "scroll":"Scroll", "starknet":"Starknet", "monad":"Monad"}


def used_assets(records):
    return {record[field] for record in records for field in ("origin_asset", "destination_asset")}


def registry_index(rows):
    if not isinstance(rows, list) or len(rows)>20000:
        raise ValueError("Invalid token registry")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid token registry entry")
        asset, network = row.get("asset_id"), row.get("blockchain")
        if (set(row)!={"asset_id", "blockchain"} or not isinstance(asset,str) or not 1<=len(asset)<=512
                or not isinstance(network,str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}",network)):
            raise ValueError("Invalid token registry identity")
        if asset in result:
            raise ValueError("Duplicate token registry asset identity")
        result[asset] = network
    return result


def build_asset_mapping(tokens, records, *, observed_at=None):
    rows = [{"asset_id":row["assetId"], "blockchain":row["blockchain"]} for row in tokens]
    index = registry_index(rows)
    value = {"schema":SCHEMA, "policy":POLICY, "source":REGISTRY_URL,
             "observed_at":int(time.time()) if observed_at is None else observed_at,
             "registry":sorted(rows,key=lambda row:row["asset_id"]),
             "assets":{asset:index.get(asset) for asset in sorted(used_assets(records))}}
    return validate_asset_mapping(value,records)


def validate_asset_mapping(value, records):
    if (not isinstance(value,dict) or set(value)!={"schema","policy","source","observed_at","registry","assets"}
            or value["schema"]!=SCHEMA or value["policy"]!=POLICY or value["source"]!=REGISTRY_URL
            or type(value["observed_at"]) is not int or not 0<=value["observed_at"]<=9007199254740991):
        raise ValueError("Invalid frozen network mapping")
    index = registry_index(value["registry"])
    expected = {asset:index.get(asset) for asset in sorted(used_assets(records))}
    if value["assets"] != expected or value["registry"]!=sorted(value["registry"],key=lambda row:row["asset_id"]):
        raise ValueError("Frozen network mapping disagrees with its registry or dataset")
    return value


async def fetch_asset_mapping(records, *, client=None):
    async with httpx.AsyncClient(timeout=45) as owned:
        response = await (client or owned).get(REGISTRY_URL)
        response.raise_for_status()
        if len(response.content)>10_000_000:
            raise ValueError("Token registry exceeds response budget")
        tokens = response.json()
    if not isinstance(tokens,list):
        raise ValueError("Token registry must be an array")
    return build_asset_mapping(tokens, records)


def network_label(asset, mapping):
    if asset not in mapping["assets"]:
        raise ValueError("Asset absent from frozen network mapping")
    code = mapping["assets"][asset]
    return "Unmapped" if code is None else LABELS.get(code,code.upper())


def mapping_summary(mapping, records):
    assets=mapping["assets"]
    return {"policy":POLICY, "sha256":sha(canonical(mapping)).hex(),
            "observed_at":mapping["observed_at"], "total_assets":len(assets),
            "resolved_assets":sum(code is not None for code in assets.values()),
            "unresolved_assets":sum(code is None for code in assets.values()),
            "total_records":len(records),
            "source_records_mapped":sum(assets[row["origin_asset"]] is not None for row in records),
            "destination_records_mapped":sum(assets[row["destination_asset"]] is not None for row in records)}


def mapping_commitment(mapping):
    # Retrieval time and unrelated registry additions cannot reroll the art seed.
    return sha(canonical({"policy":mapping["policy"],"assets":mapping["assets"]})).hex()


def mapped_seed(base_seed, mapping):
    return sha(b"NEAR_ECHOES_NETWORK_ART_V1"+bytes.fromhex(base_seed)+bytes.fromhex(mapping_commitment(mapping))).hex()
