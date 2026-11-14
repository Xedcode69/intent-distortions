"""Read-only live deployment checks. No account creation, signing or fund movement."""
import base58
from .near_rpc import NearRPC

async def validate_source_rpc(settings,rpc=None):
    rpc=rpc or NearRPC(settings.near_mainnet_rpc_url)
    if (await rpc.call("status",{}))["chain_id"]!="mainnet":raise ValueError("Source block RPC must be mainnet")
    return {"source_network":"mainnet"}

async def validate_contracts(settings,rpc=None):
    rpc=rpc or NearRPC(settings.near_rpc_url)
    status=await rpc.call("status",{})
    if status["chain_id"]!=settings.near_network:raise ValueError("Contract RPC network mismatch")
    nft=await rpc.view(settings.near_nft_contract,"get_config",{})
    auction=await rpc.view(settings.near_auction_contract,"get_config",{})
    from .testnet_profile import validate_clock_build
    validate_clock_build(settings,nft)
    validate_clock_build(settings,auction)
    version="3" if settings.economy_enabled else "2"
    if nft.get("version")!=f"echo-nft-{version}" or nft.get("auction_contract")!=settings.near_auction_contract:
        raise ValueError("NFT must use new_production with the configured auction")
    if nft.get("minter")!=settings.near_minter_account:raise ValueError("NFT minter binding mismatch")
    if auction.get("version")!=f"echo-auction-{version}" or auction.get("owner")!=settings.near_minter_account or auction.get("nft_contract")!=settings.near_nft_contract:
        raise ValueError("Auction operator/NFT binding mismatch")
    duration,extension,splits=(86400,0,[2000,8000]) if settings.economy_enabled else (604800,300,[6000,2500,1500])
    if int(auction["duration_ns"])!=duration*10**9 or int(auction["extension_ns"])!=extension*10**9 or auction["splits"]!=splits:
        raise ValueError("Auction duration, extension or treasury policy mismatch")
    treasuries=auction["treasury_accounts"]
    if len(set(treasuries))!=(1 if settings.economy_enabled else 3) or settings.near_minter_account in treasuries or settings.near_auction_contract in treasuries or settings.near_nft_contract in treasuries:
        raise ValueError("Treasury withdrawal authority must be separate")
    if settings.economy_enabled:
        if nft.get("trait_schema")!="echo-nft-traits-v1":raise ValueError("NFT contract must preserve root-level frozen trait metadata")
        economy=await rpc.view(settings.near_nft_contract,"get_economy",{})
        if economy.get("creator")!=settings.near_creator_account or economy.get("treasury")!=settings.near_treasury_account or auction.get("creator")!=settings.near_creator_account or treasuries!=[settings.near_treasury_account]:
            raise ValueError("Economy creator/treasury binding mismatch")
        if economy.get("vault_code_hash")!=settings.expected_vault_code_hash or not settings.expected_vault_code_hash:
            raise ValueError("Embedded vault WASM hash mismatch")
        if economy.get("treasury_bps")!=2000 or economy.get("vault_bps")!=8000 or economy.get("early_exit_bps_of_vault")!=4000 or economy.get("exited_ticket_reentry") is not False:
            raise ValueError("Economy financial policy mismatch")
        if settings.first_release_sunday!="2026-11-15":raise ValueError("Economy schedule requires 2026-11-15")
    for account,expected in ((settings.near_nft_contract,settings.expected_nft_code_hash),(settings.near_auction_contract,settings.expected_auction_code_hash)):
        if expected:
            result=await rpc.call("query",{"request_type":"view_account","finality":"final","account_id":account})
            if base58.b58decode(result["code_hash"]).hex()!=expected:raise ValueError("Deployed contract WASM hash mismatch")
        elif settings.enable_chain_writes:raise ValueError("Reviewed WASM hashes required for writes")
    if settings.near_market_contract:
        from .marketplace import validate_market
        await validate_market(settings,rpc)
    return {"network":settings.near_network,"contracts":"bindings_and_policy_verified","wasm_hashes_pinned":bool(settings.expected_nft_code_hash and settings.expected_auction_code_hash)}
