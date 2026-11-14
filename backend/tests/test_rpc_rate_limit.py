import httpx
import pytest
from app.services.near_rpc import NearRPC,MissingBlock
import app.services.near_rpc as module

async def test_rpc_http_200_rate_limit_backs_off_read_and_uses_fresh_response(monkeypatch):
    waits=[];requests=[]
    async def sleep(seconds):waits.append(seconds)
    monkeypatch.setattr(module.asyncio,"sleep",sleep)
    def handle(request):
        requests.append(request)
        return httpx.Response(200,json={"error":{"code":-429,"message":"private provider details"}} if len(requests)<3 else {"result":{"chain_id":"testnet"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        assert await NearRPC("https://rpc.example",client=client).call("status",{})=={"chain_id":"testnet"}
    assert waits==[1,2] and len(requests)==3

async def test_exhausted_json_rate_limit_is_bounded_and_redacted(monkeypatch):
    requests=[]
    async def sleep(_):pass
    monkeypatch.setattr(module.asyncio,"sleep",sleep)
    def handle(request):requests.append(request);return httpx.Response(200,json={"error":{"code":-429,"message":"secret credential"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError,match="rate limit") as e:await NearRPC("https://rpc.example",client=client).call("query",{})
    assert len(requests)==6 and "secret" not in str(e.value)

async def test_json_limit_does_not_rebroadcast_a_wallet_payment():
    requests=[]
    def handle(request):requests.append(request);return httpx.Response(200,json={"error":{"code":-429}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError,match="rate limit"):await NearRPC("https://rpc.example",client=client).call("send_tx",{"signed_tx_base64":"same-bytes"})
    assert len(requests)==1

async def test_unknown_historical_block_still_fails_immediately():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={"error":{"cause":{"name":"UNKNOWN_BLOCK"}}}))) as client:
        with pytest.raises(MissingBlock):await NearRPC("https://rpc.example",client=client).call("block",{"block_id":1})
