"""Public bidder prerequisites; no signing or registration side effects."""
import asyncio

from .marketplace import account
from .near_rpc import NearRPC


async def bidder_status(settings, account_id, rpc=None):
    account(account_id)
    if not settings.near_auction_contract:
        raise ValueError("Auction contract is not configured")
    rpc = rpc or NearRPC(settings.near_rpc_url, budget_seconds=8)
    async with asyncio.timeout(8):
        registered, refund = await asyncio.gather(
            rpc.view(settings.near_auction_contract, "is_bidder_registered", {"account": account_id}),
            rpc.view(settings.near_auction_contract, "get_refund", {"account": account_id}))
    if type(registered) is not bool or not isinstance(refund, str) or not refund.isascii() or not refund.isdigit() or not 0 <= int(refund) < 2**128:
        raise RuntimeError("Invalid bidder state from RPC")
    return {"account_id": account_id, "contract": settings.near_auction_contract,
            "registered": registered, "refund_yocto": refund}
