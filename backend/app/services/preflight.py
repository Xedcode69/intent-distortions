"""Read-only live deployment checks. No account creation, signing or fund movement."""
import base58
from .near_rpc import NearRPC

async def validate_contracts(settings,rpc=None):
    rpc=rpc or NearRPC(settings.near_rpc_url)
    status=await rpc.call("status",{})
    if status["chain_id"]!=settings.near_network:raise ValueError("Contract RPC network mismatch")
    nft=await rpc.view(settings.near_nft_contract,"get_config",{})
    auction=await rpc.view(settings.near_auction_contract,"get_config",{})
    if nft.get("version")!="echo-nft-2" or nft.get("auction_contract")!=settings.near_auction_contract:
        raise ValueError("NFT must use new_production with the configured auction")
    if nft.get("minter")!=settings.near_minter_account:raise ValueError("NFT minter binding mismatch")
    if auction.get("version")!="echo-auction-2" or auction.get("owner")!=settings.near_minter_account or auction.get("nft_contract")!=settings.near_nft_contract:
        raise ValueError("Auction operator/NFT binding mismatch")
    if int(auction["duration_ns"])!=604800*10**9 or int(auction["extension_ns"])!=300*10**9 or auction["splits"]!=[6000,2500,1500]:
        raise ValueError("Auction duration, extension or treasury policy mismatch")
    treasuries=auction["treasury_accounts"]
    if len(set(treasuries))!=3 or settings.near_minter_account in treasuries or settings.near_auction_contract in treasuries:
        raise ValueError("Treasury withdrawal authority must be separate")
    for account,expected in ((settings.near_nft_contract,settings.expected_nft_code_hash),(settings.near_auction_contract,settings.expected_auction_code_hash)):
        if expected:
            result=await rpc.call("query",{"request_type":"view_account","finality":"final","account_id":account})
            if base58.b58decode(result["code_hash"]).hex()!=expected:raise ValueError("Deployed contract WASM hash mismatch")
        elif settings.enable_chain_writes:raise ValueError("Reviewed WASM hashes required for writes")
    return {"network":settings.near_network,"contracts":"bindings_and_policy_verified","wasm_hashes_pinned":bool(settings.expected_nft_code_hash and settings.expected_auction_code_hash)}
