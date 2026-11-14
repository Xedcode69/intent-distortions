import base64,hashlib,json
import base58
import pytest
from fastapi import HTTPException
from app import onchain_api as media

class Chain:
    def __init__(self):
        self.network='testnet';self.code='ab'*32;self.keys=[];self.sealed=True
        self.svg='<svg xmlns="http://www.w3.org/2000/svg"></svg>';self.proof=b'{"frozen":true}';self.recipe=b'IDART1'+bytes(100)
        self.svg_hash=hashlib.sha256(self.svg.encode()).hexdigest()
    async def block(self):return {'hash':'same-finalized-block'}
    async def call(self,method,args):
        if method=='status':return {'chain_id':self.network}
        assert args['block_id']=='same-finalized-block'
        if args['request_type']=='view_account':return {'code_hash':base58.b58encode(bytes.fromhex(self.code)).decode()}
        if args['request_type']=='view_access_key_list':return {'keys':self.keys}
        name=args['method_name']
        values={'get_onchain_art':{'format':'intent-distortions-weekly-onchain-v1','sealed':self.sealed,
            'recipe_bytes':len(self.recipe),'recipe_sha256':hashlib.sha256(self.recipe).hexdigest(),
            'static_sha256':self.svg_hash,'animated_sha256':self.svg_hash,
            'commitment':{'provenance_hash':hashlib.sha256(self.proof).hexdigest()}},
            'get_static_svg':self.svg,'get_animated_svg':self.svg,
            'get_recipe_chunk':base64.b64encode(self.recipe).decode(),
            'nft_token_compact':{'metadata':{'reference':'data:application/json;base64,'+base64.b64encode(self.proof).decode()}}}
        return {'result':list(json.dumps(values[name]).encode())}

@pytest.fixture
def chain(monkeypatch):
    chain=Chain();media._cache.clear()
    monkeypatch.setattr(media,'NearRPC',lambda *args,**kwargs:chain)
    monkeypatch.setattr(media.settings,'expected_nft_code_hash','ab'*32)
    monkeypatch.setattr(media.settings,'near_nft_contract','weekly.testnet')
    return chain

@pytest.mark.parametrize('asset',['static.svg','animated.svg','recipe.bin','provenance.json'])
async def test_weekly_media_recovers_only_chain_bytes_at_one_finalized_block(chain,asset):
    response=await media.edition_asset('ECHO-000001',asset)
    assert response.body=={'static.svg':chain.svg.encode(),'animated.svg':chain.svg.encode(),'recipe.bin':chain.recipe,'provenance.json':chain.proof}[asset]
    assert 'sandbox' in response.headers['content-security-policy']

@pytest.mark.parametrize('mutation',[{'network':'mainnet'},{'code':'cd'*32},{'keys':[{'access_key':'unexpected'}]},{'sealed':False},{'svg_hash':'00'*32}])
async def test_weekly_media_refuses_wrong_identity_mutable_accounts_and_tampered_views(chain,mutation):
    for key,value in mutation.items():setattr(chain,key,value)
    with pytest.raises(HTTPException) as exc:await media.edition_asset('ECHO-000001','static.svg')
    assert exc.value.status_code==503
