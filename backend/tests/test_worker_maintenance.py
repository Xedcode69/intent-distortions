import asyncio
from types import SimpleNamespace
import pytest
from app.workers.production import Worker
from app.services.chain_writer import OutcomeUnknown

async def test_long_capture_keeps_maintenance_serialized_and_filters_success():
    finished=asyncio.Event();events=[]
    class Collector:
        async def collect(self,*args,statuses):
            assert statuses==("SUCCESS",)
            await finished.wait();return ["capture"],{"complete":True}
    class Writer:
        async def reconcile_pending(self):events.append("reconcile")
    worker=Worker.__new__(Worker);worker.collector=Collector();worker.writer=Writer()
    worker.settings=SimpleNamespace(worker_poll_seconds=.001,enable_chain_writes=True)
    async def monitor():events.append("maintenance");finished.set()
    worker.monitor=monitor
    assert await worker.collect(1,2)==(["capture"],{"complete":True})
    assert events==["reconcile","maintenance"]

async def test_unknown_signed_outcome_cancels_capture_and_stops_all_new_work():
    cancelled=asyncio.Event()
    class Collector:
        async def collect(self,*args,**kwargs):
            try:await asyncio.Event().wait()
            finally:cancelled.set()
    class Writer:
        async def reconcile_pending(self):raise OutcomeUnknown("pending exact bytes")
    worker=Worker.__new__(Worker);worker.collector=Collector();worker.writer=Writer()
    worker.settings=SimpleNamespace(worker_poll_seconds=.001,enable_chain_writes=True)
    async def monitor():raise AssertionError("Must reconcile the prior nonce first")
    worker.monitor=monitor
    with pytest.raises(OutcomeUnknown):await worker.collect(1,2)
    assert cancelled.is_set()

async def test_capture_cancellation_never_leaves_a_background_collector_running():
    cancelled=asyncio.Event()
    class Collector:
        async def collect(self,*args,**kwargs):
            try:await asyncio.Event().wait()
            finally:cancelled.set()
    worker=Worker.__new__(Worker);worker.collector=Collector();worker.settings=SimpleNamespace(worker_poll_seconds=30,enable_chain_writes=False)
    with pytest.raises(TimeoutError):await asyncio.wait_for(worker.collect(1,2),.01)
    assert cancelled.is_set()

async def test_worker_source_must_be_mainnet_even_when_contracts_are_testnet():
    from app.services.preflight import validate_source_rpc
    class RPC:
        network="testnet"
        async def call(self,method,args):return {"chain_id":self.network}
    rpc=RPC()
    with pytest.raises(ValueError,match="Source block RPC"):await validate_source_rpc(None,rpc)
    rpc.network="mainnet";assert await validate_source_rpc(None,rpc)=={"source_network":"mainnet"}
