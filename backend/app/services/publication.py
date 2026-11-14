import time
from datetime import datetime,timedelta,timezone
from ..database import Artwork,ChainEvent
from .storage import content_store
from .provenance import verify_artwork
from .chain_writer import ChainWriter
from .near_rpc import NearRPC

async def index_receipt(factory,receipt,contract,token_id,rpc):
    for outcome in receipt.get("receipts_outcome",[]):
        if outcome.get("outcome",{}).get("executor_id")!=contract:continue
        if "Failure" in outcome["outcome"].get("status",{}):continue
        for i,log in enumerate(outcome["outcome"].get("logs",[])):
            if not log.startswith("EVENT_JSON:"):continue
            import json
            event=json.loads(log[11:])
            if event.get("standard") not in ("near_echoes","nep171","near_echoes_market"):continue
            for j,data in enumerate(event.get("data",[])):
                key=f'{outcome["id"]}:{i}:{j}'
                header=(await rpc.call("block",{"block_id":outcome["block_hash"]}))["header"]
                with factory.begin() as db:
                    if not db.get(ChainEvent,key):db.add(ChainEvent(key=key,transaction_hash=receipt["transaction_hash"],receipt_id=outcome["id"],contract=contract,
                        token_id=data.get("token_id",token_id),kind=event["event"],payload=data,
                        block_height=header["height"],timestamp_ns=str(header["timestamp_nanosec"])))

async def publish(factory,settings,artwork,writer=None,rpc=None):
    rpc=rpc or NearRPC(settings.near_rpc_url);writer=writer or ChainWriter(factory,settings,rpc)
    store=content_store(settings)
    if not verify_artwork(store,artwork,True)["valid"]:raise ValueError("Artwork verification failed")
    import json
    provenance=json.loads(store.get(artwork["provenance"]["sha256"]))
    if settings.near_network!="testnet":raise ValueError("Testnet only")
    from .weekly_onchain import prepare,publish_views
    bundle=prepare(store,artwork,settings.near_nft_contract,settings.onchain_renderer_binary)
    with factory.begin() as db:
        row=db.get(Artwork,artwork["id"]);row.payload={**row.payload,"onchain_art":bundle}
    token=artwork["edition"]
    config=await rpc.view(settings.near_nft_contract,"get_config",{})
    economy=config.get("version")=="echo-nft-3"
    if economy and config.get("trait_schema")!="echo-nft-traits-v1":raise ValueError("NFT contract lacks frozen trait support; update reviewed WASM before minting")
    expected=bundle["commitment"]
    existing=await rpc.view(settings.near_nft_contract,"get_epoch_token",{"epoch":artwork["number"]})
    if existing is None:
        release=datetime.strptime(settings.first_release_sunday,"%Y-%m-%d").replace(tzinfo=timezone.utc)+timedelta(weeks=artwork["number"]-1)
        await publish_views(settings,artwork,bundle,store,writer,rpc,int(release.timestamp())*10**9)
    elif existing!=token:raise ValueError("Onchain epoch conflicts with canonical token")
    commitment=await rpc.view(settings.near_nft_contract,"get_provenance",{"token_id":token})
    if commitment!=expected:raise ValueError("Onchain commitments differ from frozen edition")
    token_view=await rpc.view(settings.near_nft_contract,"nft_token_compact",{"token_id":token})
    try:extra=json.loads(token_view["metadata"].get("extra") or "{}")
    except (ValueError,TypeError):extra={}
    if not isinstance(extra,dict):extra={}
    published_traits=extra.get("format")==bundle["format"] and all(a in extra.get("attributes",[]) for a in json.loads(bundle["metadata"]["extra"])["attributes"])
    if existing is None and not published_traits:raise ValueError("Minted NFT trait metadata mismatch")
    from ..database import Effect
    with factory.begin() as db:
        row=db.get(Artwork,artwork["id"]);effect=db.get(Effect,f'{artwork["id"]}:mint')
        row.payload={**row.payload,"nft":{"status":"minted","token_id":token,"contract":settings.near_nft_contract,
            "transaction_hash":effect.transaction_hash if effect else None,"evidence":"finalized NFT commitment view",
            "trait_status":"published" if published_traits else "legacy_missing"}}
    if economy:
        wallet=await rpc.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token})
        if wallet["wallet_status"] in ("Uncreated","Creating"):
            method="create_edition_wallet" if wallet["wallet_status"]=="Uncreated" else "reconcile_wallet"
            wallet_funding=(await rpc.view(settings.near_nft_contract,"get_economy",{}))["wallet_startup_yocto"] if method=="create_edition_wallet" else "0"
            receipt=await writer.submit(f'{artwork["id"]}:wallet:{method}:{wallet["creation_attempt"]}',settings.near_nft_contract,method,{"token_id":token},wallet_funding)
            await index_receipt(factory,receipt,settings.near_nft_contract,token,rpc)
            wallet=await rpc.view(settings.near_nft_contract,"get_edition_wallet",{"token_id":token})
        if wallet["wallet_status"] not in ("Ready","Funding","Funded"):raise ValueError("Dedicated edition wallet is not ready")
    auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token})
    if auction is None:
        owner=await rpc.view(settings.near_nft_contract,"nft_token_compact",{"token_id":token})
        if owner["owner_id"]!=settings.near_auction_contract:raise ValueError("NFT is not in auction custody")
        receipt=await writer.submit(f'{artwork["id"]}:list',settings.near_auction_contract,"create_auction",{"token_id":token},"50000000000000000000000")
        await index_receipt(factory,receipt,settings.near_auction_contract,token,rpc)
        auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token})
    if auction and auction["status"] in ("CheckingCustody","CustodyFailed"):
        from ..database import Release
        with factory() as db:
            release=db.get(Release,artwork["number"]);attempts=release.payload.get("custody_retries",0)
        if attempts>=3:raise ValueError("Custody recovery retry budget exhausted")
        receipt=await writer.submit(f'{artwork["id"]}:custody-retry:{attempts}',settings.near_auction_contract,"retry_custody",{"token_id":token})
        await index_receipt(factory,receipt,settings.near_auction_contract,token,rpc)
        with factory.begin() as db:
            release=db.get(Release,artwork["number"]);release.payload={**release.payload,"custody_retries":attempts+1}
        auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token})
    if not auction or not auction["custody_verified"]:raise ValueError("Auction custody not yet verified")
    with factory.begin() as db:
        row=db.get(Artwork,artwork["id"]);row.payload={**row.payload,"auction":auction}
    return auction
