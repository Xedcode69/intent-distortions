import pytest
import httpx
from app.config import Settings
from app.services.storage import ContentStore
from app.services import publication
import test_nft_traits

@pytest.mark.parametrize("corrupt",[False,True])
async def test_production_mint_matches_rehearsed_storage_budget_after_public_byte_checks(tmp_path,monkeypatch,corrupt):
    class PublicStore(ContentStore):
        def put(self,data):
            ref=super().put(data);return {**ref,"uri":"https://art.example/"+ref["sha256"]}
    monkeypatch.setattr(test_nft_traits,"ContentStore",PublicStore)
    store,art,_,_=test_nft_traits.saved(tmp_path)
    art.update(id="live-000001",edition="ECHO-000001",block={"hash":"block"})
    monkeypatch.setattr(publication,"content_store",lambda _:store)
    # Minimal traits fixture; full renderer/provenance validation has its own suite.
    monkeypatch.setattr(publication,"verify_artwork",lambda *args:{"valid":True})
    client_type=httpx.AsyncClient
    def transport(request):
        return httpx.Response(200,content=b"tampered" if corrupt else store.get(request.url.path[1:]))
    monkeypatch.setattr(publication.httpx,"AsyncClient",lambda **kwargs:client_type(transport=httpx.MockTransport(transport),**kwargs))
    class RPC:
        async def view(self,contract,method,args):
            if method=="get_config":return {"version":"echo-nft-3","trait_schema":"echo-nft-traits-v1"}
            if method=="get_epoch_token":return None
            raise AssertionError(method)
    class Captured(Exception):pass
    class Writer:
        calls=[]
        async def submit(self,key,contract,method,args,deposit):
            self.calls.append((method,args,deposit));raise Captured()
    writer=Writer();settings=Settings(_env_file=None,first_release_sunday="2026-11-15",near_nft_contract="nft.testnet")
    if corrupt:
        with pytest.raises(ValueError,match="Public artifact bytes differ"):await publication.publish(None,settings,art,writer,RPC())
        assert not writer.calls
    else:
        with pytest.raises(Captured):await publication.publish(None,settings,art,writer,RPC())
        method,args,deposit=writer.calls[0]
        assert method=="mint_scheduled_artwork" and deposit==str(10**24)
        assert '"Art family"' in args["metadata"]["extra"]
