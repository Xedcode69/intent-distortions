import json
from pathlib import Path
import pytest
from app.services.randomness import select_timestamp,verify_beacon,round_for
from app.services.near_rpc import NearRPC,MissingBlock

def test_deterministic_selection():
    values=[select_timestamp(i,"01"*32,100) for i in range(1,100)]
    assert values==[select_timestamp(i,"01"*32,100) for i in range(1,100)]
    assert all(100<=v<100+17*3600 for v in values)
    assert len(set(values))>90

def test_round_ceiling():
    from app.services.randomness import GENESIS_TIME
    assert round_for(GENESIS_TIME)==1
    assert round_for(GENESIS_TIME+1)==2
    assert round_for(GENESIS_TIME+30)==2

def test_rejects_wrong_round_and_bad_signature():
    beacon={"round":1,"signature":"00"*96,"previous_signature":"00"*96,"randomness":"00"*32}
    with pytest.raises(ValueError,match="round"):verify_beacon(beacon,2)
    with pytest.raises(ValueError,match="signature"):verify_beacon(beacon,1)

def test_recorded_real_beacon_when_captured():
    path=Path(__file__).resolve().parents[2]/"fixtures/sample-epoch/verified-beacon.json"
    if not path.exists(): pytest.skip("Run capture_beacon.py to record an authenticated historical beacon")
    b=json.loads(path.read_text())
    assert verify_beacon(b,b["round"])["verified"]
    with pytest.raises(ValueError):verify_beacon({**b,"randomness":"00"*32},b["round"])

async def test_block_selection_nanosecond_boundary_and_skipped_height():
    class RPC(NearRPC):
        def __init__(self):pass
        async def block(self,height=None):
            if height==3: raise MissingBlock("Skipped height")
            height=5 if height is None else height
            return {"height":height,"hash":str(height),"prev_hash":str(height-2 if height==4 else height-1),"timestamp_nanosec":str(height*1_000_000_000+2)}
        async def call(self,method,params):return {"header":await self.block(int(params["block_id"]))}
    r=await RPC().first_block_at(3)
    assert r["height"]==4
    assert int(r["previous_timestamp_ns"])<3_000_000_000<=int(r["timestamp_ns"])
    with pytest.raises(ValueError,match="not finalized"):await RPC().first_block_at(10)

async def test_recent_checkpoint_search_does_not_require_ancient_midpoints():
    class RecentOnly(NearRPC):
        def __init__(self): self.probes=[]
        async def block(self,height=None):
            height=1_000_000 if height is None else height
            self.probes.append(height)
            if height<900_000:raise AssertionError("An ancient midpoint was queried for a recent target")
            return {"height":height,"hash":str(height),"prev_hash":str(height-1),"timestamp_nanosec":str(height*10**9+2)}
        async def call(self,method,params):return {"header":await self.block(int(params["block_id"]))}
    rpc=RecentOnly();block=await rpc.first_block_at(999_000)
    assert block["height"]==999_000 and min(rpc.probes)>=900_000

async def test_rpc_retry_after_cannot_hold_a_replay_open_indefinitely():
    import httpx
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(429,headers={"Retry-After":"3600"}))) as client:
        with pytest.raises(RuntimeError,match="time budget"):
            await NearRPC("https://unit.test",client=client,budget_seconds=.05).call("status",{})
