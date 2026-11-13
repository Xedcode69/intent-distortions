import json
import time
import httpx
import pytest
import base58
from app.config import Settings
from app.services.marketplace import OneClick,checkout_amount,validate_market,NEAR

async def test_oneclick_quote_fixes_output_recipient_refund_and_preserves_deposit_memo():
    s=Settings(_env_file=None,near_intents_1click_jwt="distribution-channel-test-key")
    requests=[]
    def handle(request):
        requests.append(request)
        assert request.headers['X-API-Key']=='distribution-channel-test-key'
        if request.url.path.endswith('/tokens'):return httpx.Response(200,json=[{'assetId':'nep141:eth-usdc.omft.near','symbol':'USDC','blockchain':'eth','decimals':6}])
        p=json.loads(request.content)
        assert p['swapType']=='EXACT_OUTPUT' and p['recipient']=='buyer.near' and p['refundTo']=='0xabc'
        assert p['recipientType']=='DESTINATION_CHAIN' and p['destinationAsset']=='nep141:wrap.near'
        assert p['depositType']=='ORIGIN_CHAIN' and p['amount']==str(2*NEAR) and not p['dry']
        assert 'customRecipientMsg' not in p and 'appFees' not in p
        return httpx.Response(200,json={'quoteRequest':p,'quote':{'amountOut':p['amount'],'amountIn':'123','depositAddress':'source-address','depositMemo':'00123'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as c:
        q=await OneClick(s,c).quote(origin_asset='nep141:eth-usdc.omft.near',buyer='buyer.near',refund_to='0xabc',amount=2*NEAR,dry=False)
    assert q['quote']['depositMemo']=='00123' and len(requests)==2

async def test_quote_rejects_wrong_recipient_and_unsupported_asset():
    def handle(request):
        if request.url.path.endswith('/tokens'):return httpx.Response(200,json=[{'assetId':'token','decimals':6}])
        p=json.loads(request.content);p['recipient']='wrong.near'
        return httpx.Response(200,json={'quoteRequest':p,'quote':{'amountOut':str(NEAR)}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as c:
        api=OneClick(Settings(_env_file=None),c)
        with pytest.raises(ValueError,match='currently supported'):await api.quote(origin_asset='made-up',buyer='buyer.near',refund_to='abc',amount=NEAR)
        with pytest.raises(ValueError,match='differs'):await api.quote(origin_asset='token',buyer='buyer.near',refund_to='abc',amount=NEAR)

def test_checkout_uses_live_listing_and_leaves_gas_budget_with_buyer():
    l={'price':str(3*NEAR),'sale':None,'expires_ns':str(time.time_ns()+10**12)}
    assert checkout_amount(l)==3*NEAR+NEAR//10
    assert checkout_amount(l,str(2*NEAR))==2*NEAR+NEAR//10
    with pytest.raises(ValueError,match='unavailable'):checkout_amount({**l,'sale':{'buyer':'other.near'}})
    with pytest.raises(ValueError,match='unavailable'):checkout_amount({**l,'expires_ns':'1'})

async def test_market_preflight_checks_fee_creator_nft_capability_and_pinned_wasm():
    s=Settings(_env_file=None,near_market_contract='market.testnet',near_nft_contract='nft.testnet',near_auction_contract='auction.testnet',near_creator_account='team.testnet',expected_market_code_hash='ab'*32)
    class RPC:
        fee=500
        async def view(self,contract,method,args):
            if method=='get_economy':return {'creator':s.near_creator_account}
            if contract==s.near_nft_contract:return {'version':'echo-nft-3','auction_contract':s.near_auction_contract,'market_transfer_schema':'echo-market-transfer-v1','royalty_ownership_schema':'monthly-finalized-owner-v1'}
            return {'version':'echo-market-1','nft_contract':s.near_nft_contract,'primary_auction':s.near_auction_contract,'creator':s.near_creator_account,'fee_bps':self.fee,'currency':'NEAR','royalty_policy':'equal-per-nft-utc-cutoff-v1'}
        async def call(self,method,args):
            return {'chain_id':'testnet'} if method=='status' else {'code_hash':base58.b58encode(bytes.fromhex('ab'*32)).decode()}
    r=RPC();assert (await validate_market(s,r))['fee_bps']==500
    r.fee=0
    with pytest.raises(ValueError,match='policy'):await validate_market(s,r)

def test_marketplace_preview_does_not_fabricate_assets_or_accept_live_quotes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.marketplace_api as m
    monkeypatch.setattr(m,'settings',Settings(_env_file=None))
    app=FastAPI();app.include_router(m.router)
    with TestClient(app) as c:
        assert c.get('/api/v1/marketplace').json()['status']=='not_deployed'
        assert c.get('/api/v1/marketplace/tokens').json()==[]
        assert c.get('/api/v1/marketplace/royalties').json()==[]
        assert c.get('/api/v1/marketplace/listings?limit=1000').status_code==422
        assert c.get('/api/v1/marketplace/crosschain/tokens').status_code==409
        assert c.post('/api/v1/marketplace/crosschain/quote',json={'token_id':'ECHO-000001','listing_nonce':'1','buyer':'buyer.near','origin_asset':'token','refund_to':'source'}).status_code==409

async def test_provider_failure_never_exposes_authentication_or_response_body():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(401,text='secret provider body'))) as c:
        with pytest.raises(ValueError,match='could not fulfill') as e:await OneClick(Settings(_env_file=None),c).tokens()
    assert 'secret' not in str(e.value)

async def test_keeper_prepares_due_royalties_and_delivers_only_fixed_contract_shares(monkeypatch):
    from app.services.economy_keeper import EconomyKeeper
    import app.services.marketplace as module
    async def validated(*_):return {'next_royalty_close':202611}
    monkeypatch.setattr(module,'validate_market',validated)
    class RPC:
        async def view(self,contract,method,args):
            if method=='get_royalty_month':return {'ready':False,'pending_sales':0,'processed':25}
            if method=='get_royalty_months':return [{'cycle':202610,'ready':True,'eligible':2,'paid':1,'share':'100'}]
            if method=='get_royalty_shares':return [{'index':0,'status':'Paid'},{'index':1,'status':'Retryable'}]
            raise AssertionError(method)
    class Writer:
        rpc=RPC()
        calls=[]
        async def submit(self,key,contract,method,args,deposit='0'):
            self.calls.append((contract,method,args,deposit));return {'receipts_outcome':[]}
    s=Settings(_env_file=None,near_market_contract='market.testnet');w=Writer();k=EconomyKeeper(None,s,w)
    await k.marketplace_tick(1796083200*10**9)
    assert w.calls==[('market.testnet','prepare_royalties',{'cycle':202611},'0'),('market.testnet','pay_royalty',{'cycle':202610,'index':'1'},'1')]
    assert not any('beneficiary' in args for _,_,args,_ in w.calls)
