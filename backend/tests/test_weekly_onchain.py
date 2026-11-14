import base64,copy,hashlib
from types import SimpleNamespace
import pytest
from app.config import Settings
from app.services.weekly_onchain import publish_views
from app.services.storage import ContentStore
from app.services.collection_art import genesis

def fixture(tmp_path):
    store=ContentStore(tmp_path);recipe=b"frozen-vector-recipe"*1000
    bundle={"recipe":store.put(recipe),"recipe_bytes":len(recipe),"static":{"sha256":"ab"*32},"animated":{"sha256":"cd"*32},
        "metadata":{},"metadata_sha256":"ef"*32,"commitment":{"epoch":1,"image_hash":"ab"*32}}
    return store,bundle,{"id":"live-000001","edition":"ECHO-000001"}

class Chain:
    def __init__(self,bundle):self.bundle=bundle;self.state=None;self.data=b"";self.calls=[]
    async def view(self,contract,method,args):
        if method=="get_recipe_chunk":return base64.b64encode(self.data[args["offset"]:args["offset"]+16384]).decode()
        assert method=="get_onchain_art";return copy.deepcopy(self.state)
    async def submit(self,key,contract,method,args,deposit="0"):
        self.calls.append((key,method,deposit))
        if method=="begin_onchain_art":
            self.state={"commitment":args["commitment"],"metadata_sha256":self.bundle["metadata_sha256"],"recipe_bytes":args["recipe_bytes"],
                "recipe_sha256":args["recipe_sha256"],"static_sha256":args["static_sha256"],"animated_sha256":args["animated_sha256"],
                "uploaded_bytes":0,"static_verified":False,"animated_verified":False,"sealed":False}
        elif method=="append_onchain_recipe":
            assert args["offset"]==len(self.data);self.data+=base64.b64decode(args["data"]);self.state["uploaded_bytes"]=len(self.data)
        elif method=="verify_onchain_view":self.state[("animated" if args["animated"] else "static")+"_verified"]=True
        elif method=="mint_onchain_art":
            assert self.state["static_verified"] and self.state["animated_verified"];self.state["sealed"]=True
        else:raise AssertionError(method)

async def test_staged_upload_verifies_both_views_and_restart_never_writes_again(tmp_path):
    store,bundle,art=fixture(tmp_path);chain=Chain(bundle);settings=SimpleNamespace(near_nft_contract="weekly.testnet")
    await publish_views(settings,art,bundle,store,chain,chain,1794700800000000000)
    assert chain.data==store.get(bundle["recipe"]["sha256"])
    methods=[c[1] for c in chain.calls]
    assert methods==["begin_onchain_art","append_onchain_recipe","append_onchain_recipe","verify_onchain_view","verify_onchain_view","mint_onchain_art"]
    before=chain.calls.copy();await publish_views(settings,art,bundle,store,chain,chain,1794700800000000000)
    assert chain.calls==before

async def test_resume_rejects_changed_prefix_before_new_signing(tmp_path):
    store,bundle,art=fixture(tmp_path);chain=Chain(bundle);settings=SimpleNamespace(near_nft_contract="weekly.testnet")
    await publish_views(settings,art,bundle,store,chain,chain,1794700800000000000)
    chain.data=b"X"+chain.data[1:];before=chain.calls.copy()
    with pytest.raises(ValueError,match="prefix differs"):await publish_views(settings,art,bundle,store,chain,chain,1794700800000000000)
    assert chain.calls==before

def test_only_testnet_is_accepted_and_genesis_uses_preserved_contract():
    with pytest.raises(ValueError):Settings(_env_file=None,near_network="mainnet")
    settings=Settings(_env_file=None,execution_mode="live",onchain_art_contract="art-v1.id-operator.testnet")
    first=genesis(settings)
    assert first["number"]==0 and first["stats"]["total_swaps"]==130086
    assert first["nft"]["contract"]==settings.onchain_art_contract
    assert first["end_ns"]==settings.genesis_checkpoint_ns
