import base64
import hashlib
import httpx
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
            if event.get("standard") not in ("near_echoes","nep171"):continue
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
    async with httpx.AsyncClient(timeout=60,follow_redirects=False) as client:
        for ref in [artwork["provenance"],*provenance["files"].values()]:
            uri,digest=ref["uri"],ref["sha256"]
            if not uri.startswith("https://"):raise ValueError("Public immutable HTTPS artifacts are required")
            hasher=hashlib.sha256()
            async with client.stream("GET",uri) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():hasher.update(chunk)
            if hasher.hexdigest()!=digest:raise ValueError("Public artifact bytes differ from commitment")
    token=artwork["edition"]
    expected={"epoch":artwork["number"],"image_hash":artwork["image_hash"],"provenance_hash":artwork["provenance"]["sha256"],
              "merkle_root":artwork["merkle_root"],"seed":artwork["seed"],"block_hash":artwork["block"]["hash"]}
    existing=await rpc.view(settings.near_nft_contract,"get_epoch_token",{"epoch":artwork["number"]})
    if existing is None:
        metadata={"title":artwork["title"],"description":artwork["description"],"media":artwork["image"],
            "media_hash":base64.b64encode(bytes.fromhex(artwork["image_hash"])).decode(),"copies":1,
            "reference":artwork["provenance"]["uri"],"reference_hash":base64.b64encode(bytes.fromhex(artwork["provenance"]["sha256"])).decode()}
        receipt=await writer.submit(f'{artwork["id"]}:mint',settings.near_nft_contract,"mint_weekly_artwork",
            {"receiver_id":settings.near_auction_contract,"metadata":metadata,"commitment":expected},"100000000000000000000000")
        await index_receipt(factory,receipt,settings.near_nft_contract,token,rpc)
    elif existing!=token:raise ValueError("Onchain epoch conflicts with canonical token")
    commitment=await rpc.view(settings.near_nft_contract,"get_provenance",{"token_id":token})
    if commitment!=expected:raise ValueError("Onchain commitments differ from frozen edition")
    from ..database import Effect
    with factory.begin() as db:
        row=db.get(Artwork,artwork["id"]);effect=db.get(Effect,f'{artwork["id"]}:mint')
        row.payload={**row.payload,"nft":{"status":"minted","token_id":token,"contract":settings.near_nft_contract,
            "transaction_hash":effect.transaction_hash if effect else None,"evidence":"finalized NFT commitment view"}}
    auction=await rpc.view(settings.near_auction_contract,"get_auction",{"token_id":token})
    if auction is None:
        owner=await rpc.view(settings.near_nft_contract,"nft_token",{"token_id":token})
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
