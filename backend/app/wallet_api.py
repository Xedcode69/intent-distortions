"""Public, read-only ownership for the configured Intent Distortions collection."""
import asyncio
import re
import time

import base58
from fastapi import APIRouter, HTTPException, Query

from .config import settings
from .services.marketplace import ACCOUNT
from .services.near_rpc import NearRPC

router = APIRouter(prefix="/api/v1/wallets")


def rpc():
    return NearRPC(settings.near_rpc_url, budget_seconds=10)


@router.get("/{account_id}/collection")
async def collection(account_id: str, offset: int = Query(0, ge=0, le=100000),
                     limit: int = Query(20, ge=1, le=50)):
    if not ACCOUNT.fullmatch(account_id):
        raise HTTPException(422, "Valid NEAR account required")
    result = {"account_id": account_id, "network": settings.near_network,
              "contract": settings.near_nft_contract, "offset": offset, "limit": limit}
    if not settings.near_nft_contract:
        return {**result, "status": "not_deployed", "tokens": [], "total": None, "checked_at": None}
    if not re.fullmatch(r"[a-f0-9]{64}", settings.expected_nft_code_hash):
        raise HTTPException(409, "Pin the reviewed NFT contract hash before reading this collection")

    # Never turn this into an arbitrary account/contract RPC proxy. Only the
    # configured collection is queried, and its network/code identity is checked.
    try:
        r = rpc()
        chain, code = await asyncio.gather(
            r.call("status", {}),
            r.call("query", {"request_type": "view_account", "account_id": settings.near_nft_contract, "finality": "final"}),
        )
        if chain["chain_id"] != settings.near_network or base58.b58decode(code["code_hash"]).hex() != settings.expected_nft_code_hash:
            raise ValueError("Collection identity mismatch")
        tokens, total = await asyncio.gather(
            r.view(settings.near_nft_contract, "nft_tokens_for_owner", {"account_id": account_id, "from_index": str(offset), "limit": limit}),
            r.view(settings.near_nft_contract, "nft_supply_for_owner", {"account_id": account_id}),
        )
        if (not isinstance(total, str) or not re.fullmatch(r"\d{1,39}", total)
                or not isinstance(tokens, list) or len(tokens) > limit
                or any(not isinstance(token, dict) or token.get("owner_id") != account_id
                       or not isinstance(token.get("token_id"), str) for token in tokens)
                or len({token["token_id"] for token in tokens}) != len(tokens)):
            raise ValueError("Invalid collection response")
    except Exception:
        # RPC URLs may contain credentials; provider exceptions are private.
        raise HTTPException(503, "Live collection could not be verified. Try again shortly.") from None
    from .services.weekly_onchain import resolve_media
    return {**result, "status": "onchain", "tokens": [resolve_media(t,settings.near_nft_contract) for t in tokens], "total": total, "checked_at": int(time.time())}
