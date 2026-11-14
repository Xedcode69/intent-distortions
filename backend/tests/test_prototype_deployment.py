import base64,hashlib,json
import pytest
from app.services.signed_call import inspect_signed_bootstrap

def encoded(action=0,deposit=123,trailing=b''):
    def num(n,size):return n.to_bytes(size,'little')
    def vec(b):return num(len(b),4)+b
    code=b'wasm-code';args={'minter':'operator.testnet'}
    expected={'signer':'operator.testnet','contract':'weekly.operator.testnet','deposit_yocto':'123',
        'code_sha256':hashlib.sha256(code).hexdigest(),'method':'new','args':args,'gas':60*10**12}
    data=vec(expected['signer'].encode())+b'\0'+bytes(32)+num(7,8)+vec(expected['contract'].encode())+bytes(32)
    data+=num(4,4)+bytes([action,3])+num(deposit,16)+b'\1'+vec(code)+b'\2'+vec(b'new')+vec(json.dumps(args).encode())+num(expected['gas'],8)+num(0,16)+b'\0'+bytes(64)+trailing
    return base64.b64encode(data).decode(),expected

def test_bootstrap_inspector_accepts_only_exact_keyless_plan():
    data,expected=encoded();assert inspect_signed_bootstrap(data,expected)['nonce']==7

@pytest.mark.parametrize('kwargs',[{'action':5},{'deposit':124},{'trailing':b'key'}])
def test_bootstrap_rejects_extra_keys_changed_funding_and_trailing_bytes(kwargs):
    data,expected=encoded(**kwargs)
    with pytest.raises(ValueError):inspect_signed_bootstrap(data,expected)
