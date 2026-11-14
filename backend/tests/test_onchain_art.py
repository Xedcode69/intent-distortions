import base64
import copy
import hashlib
import json
from types import SimpleNamespace
import base58
import pytest
from app.services.onchain_art import pack_scene,motion_controls,quantize
from app.services.onchain_reader import snapshot,recover_asset,FORMAT

FEATURES={'burstiness':.4,'flow_imbalance':.2,'route_diversity':.6,'reciprocity':.7,'size_inequality':.8,'community_count':3}
def scene():
    return {'version':'echo-renderer-4','width':1440,'height':1440,'background_style':{'top':'#080c13','bottom':'#102030'},
            'animation':{'period_seconds':32,'pulse_hz':.15,'activity_profile':[.5]*48},
            'shapes':[{'kind':'dot','layer':'particles','color':'#88aaff','alpha':200,'center':[720.001,710.002],'radius':1.234}]}

def test_packed_geometry_is_fixed_precision_and_reproducible():
    source=scene();motion=motion_controls(FEATURES,'crystalline','01'*32)
    first=pack_scene(source,motion)
    assert first.startswith(b'IDART1') and first==pack_scene(source,motion)
    assert len(first)<120 and int.from_bytes(first[-9:-6],'big')==1234
    assert int.from_bytes(first[-6:-3],'big')==720001
    assert source==scene() and quantize(.0005)==1
    changed=copy.deepcopy(source);changed['shapes'][0]['center'][0]+=.001
    assert pack_scene(changed,motion)!=first

@pytest.mark.parametrize('mutation',[lambda s:s['shapes'][0].update(color='url(https://bad.example)'),
    lambda s:s['shapes'][0].update(center=[float('nan'),1]),lambda s:s['shapes'][0].update(center=[2000,1]),
    lambda s:s.update(width=10000),lambda s:s['shapes'][0].update(alpha=256),
    lambda s:s['animation'].update(activity_profile=[1]*47)])
def test_packer_rejects_nonportable_or_unbounded_art(mutation):
    value=scene();mutation(value)
    with pytest.raises((ValueError,OverflowError)):
        pack_scene(value,motion_controls(FEATURES,'crystalline','01'*32))

def test_statistics_change_frozen_motion_without_rerolling_geometry():
    first=motion_controls(FEATURES,'crystalline','01'*32)
    second=motion_controls({**FEATURES,'burstiness':.9,'flow_imbalance':.8},'crystalline','01'*32)
    assert first['strength']!=second['strength'] and first['direction']!=second['direction']
    assert first['route_period_ms']!=second['route_period_ms'] and first['profile']==second['profile']==2

class RPC:
    def __init__(self):
        self.code='ab'*32;self.network='testnet';self.keys=[];self.svg='<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        self.recipe=b'IDART1'+b'x'*100
        self.edition={'format':FORMAT,'token_id':'ART-1','sealed':True,'recipe_bytes':len(self.recipe),'uploaded_bytes':len(self.recipe),
            'recipe_sha256':hashlib.sha256(self.recipe).hexdigest(),'static_sha256':hashlib.sha256(self.svg.encode()).hexdigest(),
            'animated_sha256':hashlib.sha256(self.svg.encode()).hexdigest(),'artwork_commitment':'cd'*32}
    async def block(self):return {'height':123,'hash':'one-finalized-block'}
    async def call(self,method,args):
        if method=='status':return {'chain_id':self.network}
        assert args['block_id']=='one-finalized-block'
        if args['request_type']=='view_account':return {'code_hash':base58.b58encode(bytes.fromhex(self.code)).decode(),'storage_usage':1000}
        if args['request_type']=='view_access_key_list':return {'keys':self.keys}
        name=args['method_name'];arguments=json.loads(base64.b64decode(args['args_base64']))
        value=({'get_config':{'format':FORMAT,'renderer':'idart1-svg-1','external_dependencies':False,'upgrade_method':False},
                'get_edition':self.edition,'get_static_svg':self.svg,'get_animated_svg':self.svg,
                'get_recipe_chunk':base64.b64encode(self.recipe[arguments.get('offset',0):]).decode()})[name]
        return {'result':list(json.dumps(value).encode())}

def settings():return SimpleNamespace(onchain_art_contract='art.testnet',onchain_art_token_id='ART-1',expected_onchain_art_code_hash='ab'*32,near_network='testnet')

async def test_reader_checks_code_keys_and_recovers_only_chain_bytes():
    rpc=RPC();config=settings();state=await snapshot(config,rpc)
    assert state['keyless'] and state['block_height']==123
    assert await recover_asset(config,rpc,state,'static')==rpc.svg.encode()
    assert await recover_asset(config,rpc,state,'recipe')==rpc.recipe
    rpc.svg='<svg changed="yes"></svg>'
    with pytest.raises(ValueError,match='hash mismatch'):await recover_asset(config,rpc,state,'static')

@pytest.mark.parametrize('change',[{'code':'ef'*32},{'network':'mainnet'},{'edition':{'format':FORMAT,'sealed':False}}])
async def test_reader_rejects_wrong_identity_or_unsealed_editions(change):
    rpc=RPC()
    for name,value in change.items():setattr(rpc,name,value)
    with pytest.raises(ValueError):await snapshot(settings(),rpc)

async def test_reader_reports_existing_keys_without_claiming_final_account_lock():
    rpc=RPC();rpc.keys=[{'public_key':'a-public-key'}]
    assert not (await snapshot(settings(),rpc))['keyless']

def test_unconfigured_prototype_has_no_synthetic_onchain_success(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.config import Settings
    import app.onchain_api as module
    monkeypatch.setattr(module,'settings',Settings(_env_file=None,onchain_art_contract=''))
    app=FastAPI();app.include_router(module.router)
    with TestClient(app) as client:
        assert client.get('/api/v1/onchain/prototype').status_code==404
        assert client.get('/api/v1/onchain/prototype/static.svg').status_code==404
        assert client.post('/api/v1/onchain/prototype').status_code==405

def test_signed_calls_are_hashed_before_broadcast_and_bound_to_the_exact_intent():
    from app.services.signed_call import inspect_signed_call
    def vector(value):return len(value).to_bytes(4,'little')+value
    expected={'signer':'operator.testnet','contract':'art.operator.testnet','method':'append_recipe',
              'args':{'token_id':'ART-1','offset':0,'data':'AA=='},'deposit_yocto':'0','gas':80*10**12}
    unsigned=(vector(expected['signer'].encode())+b'\x00'+b'p'*32+(100).to_bytes(8,'little')+
        vector(expected['contract'].encode())+b'b'*32+(1).to_bytes(4,'little')+b'\x02'+
        vector(expected['method'].encode())+vector(json.dumps(expected['args']).encode())+
        expected['gas'].to_bytes(8,'little')+(0).to_bytes(16,'little'))
    encoded=base64.b64encode(unsigned+b'\x00'+b's'*64).decode()
    info=inspect_signed_call(encoded,expected)
    assert info['transaction_hash']==base58.b58encode(hashlib.sha256(unsigned).digest()).decode() and info['nonce']==100
    for changed in ({**expected,'contract':'other.testnet'},{**expected,'gas':200*10**12},{**expected,'deposit_yocto':'1'},
                    {**expected,'args':{**expected['args'],'offset':1}}):
        with pytest.raises(ValueError,match='authorized call'):inspect_signed_call(encoded,changed)
    with pytest.raises(ValueError):inspect_signed_call(base64.b64encode(unsigned+b'\x00'+b's'*63).decode(),expected)
