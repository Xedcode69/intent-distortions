"""Use the official near-cli-rs OS keychain signer. No secret values in arguments.

This is an opt-in testnet-only runner, not a claim of an already completed mint.
Requires deployed initialized contracts, funded accounts and public HTTPS/IPFS URIs.
"""
import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.config import settings
from app.database import init_db,Artwork
from app.services.near_rpc import NearRPC
from app.services.provenance import verify_artwork
from app.services.storage import content_store
from app.services.canonical_data import sha
from app.services.nft_traits import publish_traits,token_metadata

def call(contract,method,args,signer,deposit="0 NEAR"):
    # Structured argv, no shell, no key material. An uncertain CLI outcome is
    # never automatically resubmitted: the next invocation queries chain first.
    command=["near","contract","call-function","as-transaction",contract,method,"json-args",json.dumps(args),
        "prepaid-gas","200 Tgas","attached-deposit",deposit,"sign-as",signer,"network-config","testnet","sign-with-keychain","send"]
    subprocess.run(command,check=True)

async def main():
    parser=argparse.ArgumentParser();parser.add_argument("--edition",default="demo-000001")
    parser.add_argument("--minter",required=True);parser.add_argument("--bidder-a",required=True);parser.add_argument("--bidder-b",required=True)
    parser.add_argument("--media-uri",required=True);parser.add_argument("--provenance-uri",required=True)
    parser.add_argument("--traits-uri",help="Public immutable HTTPS/IPFS URL of exported nft-traits.json; S3 publication supplies it automatically")
    parser.add_argument("--bid-a",default="1 NEAR");parser.add_argument("--bid-b",default="1.1 NEAR")
    parser.add_argument("--wait-for-end",action="store_true");a=parser.parse_args()
    if settings.near_network!="testnet":raise SystemExit("This runner supports testnet only")
    if settings.execution_mode=="testnet_rehearsal":raise SystemExit("Use scripts/testnet_rehearsal.py mint for this isolated workspace; the full bidding runner is disabled here")
    if not shutil.which("near"):raise SystemExit("Install near-cli-rs and configure your testnet OS keychain accounts first")
    if not settings.near_nft_contract or not settings.near_auction_contract:raise SystemExit("Configure both deployed testnet contracts")
    for uri in [a.media_uri,a.provenance_uri,*([a.traits_uri] if a.traits_uri else [])]:
        if not uri.startswith(("https://","ipfs://")):raise SystemExit("Public immutable media/provenance URI required; local URLs are not publishable")
    factory=init_db();rpc=NearRPC(settings.near_rpc_url)
    with factory() as db:
        row=db.get(Artwork,a.edition)
        if not row:raise SystemExit("Run the local pipeline first")
        artwork=row.payload
    store=content_store(settings)
    assert verify_artwork(store,artwork)["valid"]
    p=json.loads(store.get(artwork["provenance"]["sha256"]))
    traits,traits_ref=publish_traits(store,artwork)
    a.traits_uri=a.traits_uri or traits_ref["uri"]
    if not a.traits_uri.startswith(("https://","ipfs://")):raise SystemExit("Upload exported nft-traits.json and pass --traits-uri, or configure S3 publication")
    traits_ref={**traits_ref,"uri":a.traits_uri}
    import httpx
    async with httpx.AsyncClient(timeout=60,follow_redirects=True) as client:
        for uri,expected in [(a.media_uri,artwork["image_hash"]),(a.provenance_uri,artwork["provenance"]["sha256"]),(a.traits_uri,traits["sha256"])]:
            url="https://ipfs.io/ipfs/"+uri[7:] if uri.startswith("ipfs://") else uri
            response=await client.get(url);response.raise_for_status()
            if sha(response.content).hex()!=expected:raise SystemExit("Public URI bytes do not match frozen content commitment")
    token_id=artwork["edition"]
    config=await rpc.view(settings.near_nft_contract,"get_config",{})
    economy=config.get("version")=="echo-nft-3"
    if economy and config.get("trait_schema")!="echo-nft-traits-v1":raise SystemExit("Deploy reviewed trait-capable NFT WASM before minting")
    existing=await rpc.view(settings.near_nft_contract,"get_epoch_token",{"epoch":artwork["number"]})
    if existing is None:
        metadata=token_metadata(artwork,traits,traits_ref,a.media_uri,a.provenance_uri)
        commitment={"epoch":artwork["number"],"image_hash":artwork["image_hash"],"provenance_hash":artwork["provenance"]["sha256"],"merkle_root":artwork["merkle_root"],"seed":artwork["seed"],"block_hash":artwork["block"]["hash"]}
        if economy:
            if settings.first_release_sunday!="2026-11-15":raise SystemExit("Economy requires FIRST_RELEASE_SUNDAY=2026-11-15")
            release=datetime(2026,11,15,tzinfo=timezone.utc)+timedelta(weeks=artwork["number"]-1)
            call(settings.near_nft_contract,"mint_scheduled_artwork",{"release_ns":str(int(release.timestamp())*10**9),"metadata":metadata,"commitment":commitment},a.minter,"0.1 NEAR")
        else:
            call(settings.near_nft_contract,"mint_weekly_artwork",{"receiver_id":settings.near_auction_contract,"metadata":metadata,"commitment":commitment},a.minter,"0.1 NEAR")
    elif existing!=token_id:raise SystemExit("Onchain epoch token conflicts with local edition")
    commitment=await rpc.view(settings.near_nft_contract,"get_provenance",{"token_id":token_id})
    if commitment["image_hash"]!=artwork["image_hash"]:raise SystemExit("Onchain image commitment mismatch")
    with factory.begin() as db:
        row=db.get(Artwork,a.edition)
        row.payload={**row.payload,"nft":{"status":"minted","token_id":token_id,"contract":settings.near_nft_contract,"transaction_hash":None,"evidence":"finalized contract view; receipt hash available in near-cli output"}}
    if economy:
        wallet=await rpc.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token_id})
        if wallet["wallet_status"]=="Uncreated":call(settings.near_nft_contract,"create_edition_wallet",{"token_id":token_id},a.minter)
        elif wallet["wallet_status"]=="Creating":call(settings.near_nft_contract,"reconcile_wallet",{"token_id":token_id},a.minter)
        wallet=await rpc.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token_id})
        if wallet["wallet_status"]!="Ready" and wallet["cycle"] is None:raise SystemExit("Fund the coordinator operating reserve and reconcile wallet creation")
        if int(wallet["release_ns"])<1796515200*10**9:
            print(json.dumps({"status":"CreatorMinted","edition_wallet":wallet,"owner":(await rpc.view(settings.near_nft_contract,"nft_token",{"token_id":token_id}))["owner_id"]},indent=2));return
    auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token_id})
    if auction is None:
        call(settings.near_auction_contract,"create_auction",{"token_id":token_id},a.minter,"0.05 NEAR")
    auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token_id})
    if auction["status"]=="Active" and int(auction["highest_bid"])==0:
        for who in [a.bidder_a,a.bidder_b]:
            # Registration can be checked from the dedicated method without submitting twice.
            registered=await rpc.view(settings.near_auction_contract,"is_bidder_registered",{"account":who})
            if not registered:call(settings.near_auction_contract,"register_bidder",{},who,"0.01 NEAR")
        call(settings.near_auction_contract,"place_bid",{"token_id":token_id},a.bidder_a,a.bid_a)
        call(settings.near_auction_contract,"place_bid",{"token_id":token_id},a.bidder_b,a.bid_b)
    elif auction["status"]=="Active":
        print("Existing bids detected. Preserving them; inspect onchain state before any additional bid.")
    if a.wait_for_end:
        while True:
            auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token_id})
            latest=await rpc.block()
            if int(latest["timestamp_nanosec"])>=int(auction["end_ns"]):break
            await asyncio.sleep(5)
        if auction["status"] in ("Active","RecoveryRequired"):
            call(settings.near_auction_contract,"finalize_auction",{"token_id":token_id},a.minter)
        auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token_id})
        if auction["status"]!="Settled":raise SystemExit("Auction did not settle; inspect receipts and custody")
        token=await rpc.view(settings.near_nft_contract,"nft_token",{"token_id":token_id})
        if token["owner_id"]!=auction["highest_bidder"]:raise SystemExit("Winner ownership mismatch")
        if economy:
            wallet=await rpc.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token_id})
            if wallet["wallet_status"]=="Ready":call(settings.near_nft_contract,"fund_edition_wallet",{"token_id":token_id},a.minter)
            wallet=await rpc.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token_id})
            if wallet["wallet_status"]!="Funded":raise SystemExit("Inspect vault funding receipts")
        refund=await rpc.view(settings.near_auction_contract,"get_refund",{"account":a.bidder_a})
        if int(refund)>0:call(settings.near_auction_contract,"claim_refund",{},a.bidder_a,"1 yoctoNEAR")
        print("Verified finalized NFT ownership, auction settlement, and losing-bidder refund.")
    print(json.dumps(await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token_id}),indent=2))

if __name__=="__main__":asyncio.run(main())
