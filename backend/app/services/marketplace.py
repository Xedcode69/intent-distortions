"""Pinned on-chain marketplace views and non-custodial 1Click funding quotes."""
import re
import time
from datetime import datetime,timedelta,timezone
import base58
import httpx

ONECLICK="https://1click.chaindefuser.com/v0"
NEAR=10**24
ACCOUNT=re.compile(r"^(?=.{2,64}$)[a-z0-9]+(?:[._-][a-z0-9]+)*$")

def account(value):
    if not ACCOUNT.fullmatch(value):raise ValueError("Valid NEAR account required")
    return value

async def validate_market(settings,rpc):
    config=await rpc.view(settings.near_market_contract,"get_config",{})
    expected={"version":"echo-market-1","nft_contract":settings.near_nft_contract,"primary_auction":settings.near_auction_contract,
        "creator":settings.near_creator_account,"fee_bps":500,"royalty_policy":"equal-per-nft-utc-cutoff-v1","currency":"NEAR"}
    if any(config.get(k)!=v for k,v in expected.items()):raise ValueError("Marketplace contract policy mismatch")
    nft=await rpc.view(settings.near_nft_contract,"get_config",{})
    if nft.get("version")!="echo-nft-3" or nft.get("auction_contract")!=settings.near_auction_contract:raise ValueError("Marketplace requires the configured economy NFT")
    if nft.get("market_transfer_schema")!="echo-market-transfer-v1" or nft.get("royalty_ownership_schema")!="monthly-finalized-owner-v1":raise ValueError("NFT lacks conditional transfers or historical royalty ownership support")
    economy=await rpc.view(settings.near_nft_contract,"get_economy",{})
    if economy.get("creator")!=settings.near_creator_account:raise ValueError("Marketplace creator differs from the NFT economy")
    chain=await rpc.call("status",{})
    if chain["chain_id"]!=settings.near_network:raise ValueError("Marketplace RPC network mismatch")
    if not settings.expected_market_code_hash:raise ValueError("Pin reviewed marketplace WASM before enabling trades")
    code=await rpc.call("query",{"request_type":"view_account","account_id":settings.near_market_contract,"finality":"final"})
    if base58.b58decode(code["code_hash"]).hex()!=settings.expected_market_code_hash:raise ValueError("Marketplace WASM hash mismatch")
    if settings.expected_nft_code_hash:
        nft_code=await rpc.call("query",{"request_type":"view_account","account_id":settings.near_nft_contract,"finality":"final"})
        if base58.b58decode(nft_code["code_hash"]).hex()!=settings.expected_nft_code_hash:raise ValueError("Marketplace NFT WASM hash mismatch")
    return config

class OneClick:
    def __init__(self,settings,client=None):self.settings=settings;self.client=client
    async def request(self,method,path,**kwargs):
        headers={"X-API-Key":self.settings.near_intents_1click_jwt} if self.settings.near_intents_1click_jwt else {}
        async def run(client):
            response=await client.request(method,ONECLICK+path,headers=headers,**kwargs)
            if response.status_code==429:raise ValueError("Swap provider is busy; try again later")
            if response.status_code>=400:raise ValueError("Swap provider could not fulfill this request")
            return response.json()
        if self.client:return await run(self.client)
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:return await run(client)
    async def tokens(self):
        rows=await self.request("GET","/tokens")
        if not isinstance(rows,list):raise ValueError("Invalid swap token catalog")
        return [{k:r.get(k) for k in ("assetId","symbol","blockchain","decimals","contractAddress")} for r in rows if isinstance(r,dict) and r.get("assetId") and isinstance(r.get("decimals"),int)]
    async def quote(self,*,origin_asset,buyer,refund_to,amount,dry=True):
        account(buyer)
        if not 1<=amount<=10**33:raise ValueError("Checkout amount exceeds supported bounds")
        catalog=await self.tokens()
        token=next((r for r in catalog if r["assetId"]==origin_asset),None)
        if token is None:raise ValueError("Choose a currently supported source asset")
        if not refund_to or len(refund_to)>256 or any(ord(c)<33 for c in refund_to):raise ValueError("Origin-chain refund address required")
        payload={"dry":dry,"swapType":"EXACT_OUTPUT","slippageTolerance":100,"originAsset":origin_asset,
            "destinationAsset":"nep141:wrap.near","depositType":"ORIGIN_CHAIN","recipientType":"DESTINATION_CHAIN",
            "refundType":"ORIGIN_CHAIN","recipient":buyer,"refundTo":refund_to,"amount":str(amount),
            "deadline":(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat().replace("+00:00","Z")}
        result=await self.request("POST","/quote",json=payload)
        echoed=result.get("quoteRequest",{})
        if any(echoed.get(k)!=payload[k] for k in ("recipient","refundTo","originAsset","destinationAsset","amount","swapType","depositType","recipientType","refundType","dry")):
            raise ValueError("Swap quote differs from requested funding destination")
        q=result.get("quote",{})
        if int(q.get("amountOut","0"))<amount or not dry and not q.get("depositAddress"):raise ValueError("Incomplete swap quote")
        return result

def checkout_amount(listing,offer_amount=None):
    if listing.get("sale") or int(listing["expires_ns"])<=time.time_ns():raise ValueError("Listing is unavailable")
    amount=int(offer_amount) if offer_amount else int(listing.get("price") or 0)
    if amount<=0:raise ValueError("Positive price or offer required")
    # Additional output is the buyer's money, covering account registration,
    # offer storage and native gas. It is never sent directly to the seller.
    return amount+NEAR//10
