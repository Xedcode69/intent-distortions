import httpx
import pytest
from app.services.intents_collector import Collector
from test_dataset import raw

async def no_sleep(seconds):pass

async def test_pagination_query_boundaries_and_memo():
    calls=[]
    def handler(request):
        calls.append(dict(request.url.params))
        assert request.headers["Authorization"]=="Bearer partner"
        return httpx.Response(200,json=[raw(1,101,depositMemo="memo"),raw(2,100)] if len(calls)==1 else [])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records,evidence=await Collector("https://example.test","partner",client,no_sleep).collect(100,200,2)
    assert len(records)==2 and evidence["complete"]
    assert calls[0]["startTimestampUnix"]=="99"
    assert calls[1]["lastDepositAddress"]=="deposit-2"
    assert "lastDepositMemo" not in calls[1]

async def test_rate_limit_retry():
    count=0
    def handler(request):
        nonlocal count;count+=1
        return httpx.Response(429,headers={"Retry-After":"5"}) if count==1 else httpx.Response(200,json=[])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records,evidence=await Collector("https://example.test","partner",client,no_sleep).collect(100,200)
    assert count==2 and evidence["complete"]

async def test_invalid_response_and_stalled_pagination():
    for response in [{"not":"array"},[raw()]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=response))) as client:
            with pytest.raises(ValueError): await Collector("https://example.test","partner",client,no_sleep).collect(100,200,1)

async def test_network_error_exhausts_budget():
    def handler(request):raise httpx.ConnectError("offline")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.ConnectError):await Collector("https://example.test","partner",client,no_sleep).collect(100,200)

async def test_success_only_filter_survives_pagination_and_excludes_boundary_overlap():
    calls=[]
    def handler(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200,json=[raw(1,101),raw(2,99)] if len(calls)==1 else [raw(3,100)])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records,evidence=await Collector("https://example.test","partner",client,no_sleep).collect(
            100,200,2,statuses=("SUCCESS",))
    assert len(records)==2 and evidence["complete"]
    assert evidence["query"]["statuses"]=="SUCCESS"
    assert all(call["statuses"]=="SUCCESS" and call["startTimestampUnix"]=="99"
               and call["endTimestampUnix"]=="200" for call in calls)
    assert all("showTestTxs" not in call for call in calls)

async def test_success_only_filter_rejects_provider_status_mismatch():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _:httpx.Response(200,json=[raw(status="FAILED")]))) as client:
        with pytest.raises(ValueError,match="status filter"):
            await Collector("https://example.test","partner",client,no_sleep).collect(
                100,200,statuses=("SUCCESS",))
