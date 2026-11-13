import math
from collections import Counter
from decimal import Decimal

def chain(asset, asset_mapping=None):
    if asset_mapping is not None:
        from .asset_networks import network_label
        return network_label(asset,asset_mapping)
    # Recognize explicit chain prefixes only; never guess a chain from a hashed token.
    value = asset.removeprefix("nep141:")
    for prefix, label in {"eth-": "Ethereum", "base-": "Base", "sol-": "Solana", "btc-": "Bitcoin", "arb-": "Arbitrum", "near:": "NEAR"}.items():
        if value.startswith(prefix):
            return label
    if value in ("wrap.near", "near", "usdt.tether-token.near"):
        return "NEAR"
    return "Unmapped"

def statistics(records, start, end, asset_mapping=None):
    resolve=lambda asset:chain(asset,asset_mapping)
    sources = Counter(resolve(r["origin_asset"]) for r in records)
    routes = Counter(f'{resolve(r["origin_asset"])} → {resolve(r["destination_asset"])}' for r in records)
    n, k = len(records), len(sources)
    diversity = -sum((c/n)*math.log(c/n) for c in sources.values())/math.log(k) if k > 1 else 0
    if asset_mapping is not None:
        known={name:count for name,count in sources.items() if name!="Unmapped"}
        k, mapped = len(known), sum(known.values())
        diversity=-sum((count/mapped)*math.log(count/mapped) for count in known.values())/math.log(k) if k>1 else 0
    bins = [0]*24
    for r in records:
        bins[min(23, int(24*(r["created_at_unix"]-start)/(end-start)))] += 1
    volumes = [Decimal(r["amount_in_usd"]) for r in records if r["amount_in_usd"] is not None]
    result = {"total_swaps": n, "unique_chains": k, "chain_diversity_score": round(diversity, 6),
            "chains": dict(sorted(sources.items())), "dominant_routes": dict(routes.most_common(6)),
            "activity": bins, "public_volume_usd": str(sum(volumes, Decimal(0))), "volume_coverage": len(volumes),
            "particle_count": min(2400, int(100*math.sqrt(n)))}
    if asset_mapping is not None:
        from .asset_networks import mapping_summary
        result["network_mapping"]=mapping_summary(asset_mapping,records)
    return result
