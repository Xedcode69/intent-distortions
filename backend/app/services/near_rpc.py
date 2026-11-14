import base64
import json
import httpx
import asyncio

class MissingBlock(ValueError):
    pass

class NearRPC:
    def __init__(self, url, *, client=None, budget_seconds=90):
        self.url = url
        self.client = client
        self.budget_seconds = budget_seconds

    async def call(self, method, params):
        try:
            async with asyncio.timeout(self.budget_seconds):
                return await self._call(method,params)
        except TimeoutError:
            raise RuntimeError("NEAR RPC time budget exhausted; configure a healthy provider") from None

    async def _call(self, method, params):
        async with httpx.AsyncClient(timeout=30) as owned:
            client=self.client or owned
            for attempt in range(6):
                response = await client.post(self.url, json={"jsonrpc": "2.0", "id": "echoes", "method": method, "params": params})
                payload=response.json() if response.status_code<400 else None
                # Some providers return JSON-RPC -429 with HTTP 200. Back off
                # read calls as well as HTTP limits; never expose provider bodies.
                rpc_limited=isinstance(payload,dict) and isinstance(payload.get("error"),dict) and payload["error"].get("code") in (-429,429)
                retry_read=rpc_limited and method in ("query","status","block","tx","EXPERIMENTAL_tx_status")
                if response.status_code==429 or response.status_code>=500 or retry_read:
                    if attempt==5: break
                    try:retry_after=min(30,max(0,float(response.headers.get("Retry-After",0))))
                    except ValueError:retry_after=0
                    await asyncio.sleep(max(retry_after,2**attempt))
                    continue
                break
            if response.status_code>=400:
                raise RuntimeError(f"NEAR RPC HTTP {response.status_code}; use a healthy archival provider")
            if rpc_limited:raise RuntimeError("NEAR RPC rate limit reached; wait before retrying or configure a provider with sufficient capacity")
            if "error" in payload:
                error=payload["error"]
                name=error.get("cause",{}).get("name",error.get("name","query_error"))
                if name in ("UNKNOWN_BLOCK","DB_NOT_FOUND_ERROR"):
                    raise MissingBlock("Historical block unavailable or skipped")
                raise RuntimeError(f"NEAR RPC query failed: {name}")
            return payload["result"]

    async def block(self, height=None):
        return (await self.call("block", {"block_id": height} if height is not None else {"finality": "final"}))["header"]

    async def predecessor(self, selected):
        try:
            previous = (await self.call("block", {"block_id": selected["prev_hash"]}))["header"]
        except MissingBlock:
            # Some archival providers retain height lookup but not the hash index.
            # A numeric candidate is valid only if it matches the exact parent hash.
            declared = selected.get("prev_height")
            start = declared if type(declared) is int and 0 < declared < selected["height"] else selected["height"] - 1
            for height in range(start, max(0, start - 8), -1):
                try:
                    candidate = await self.block(height)
                except MissingBlock:
                    continue
                if candidate["hash"] == selected["prev_hash"]:
                    previous = candidate
                    break
            else:
                raise ValueError("Exact historical predecessor unavailable from archival RPC") from None
        if previous["hash"] != selected["prev_hash"] or previous["height"] >= selected["height"]:
            raise ValueError("Historical predecessor hash or height mismatch")
        return previous

    async def view(self, contract, method, args):
        result = await self.call("query", {"request_type": "call_function", "finality": "final", "account_id": contract,
                                 "method_name": method, "args_base64": base64.b64encode(json.dumps(args).encode()).decode()})
        return json.loads(bytes(result["result"]))

    async def verify_selected_block(self,block,target_seconds):
        selected=await self.block(block["height"])
        previous=await self.predecessor(selected)
        finalized=await self.block()
        if selected["hash"]!=block["hash"] or str(selected["timestamp_nanosec"])!=str(block["timestamp_ns"]):
            raise ValueError("Recorded block differs from archival RPC")
        if str(previous["timestamp_nanosec"])!=str(block["previous_timestamp_ns"]):
            raise ValueError("Recorded predecessor timestamp differs from archival RPC")
        if selected["height"]>finalized["height"] or not int(previous["timestamp_nanosec"])<target_seconds*10**9<=int(selected["timestamp_nanosec"]):
            raise ValueError("Selected block is not the first finalized block at target")
        return True

    async def first_block_at(self, timestamp_seconds):
        try:
            return await asyncio.wait_for(self._first_block_at(timestamp_seconds),timeout=180)
        except TimeoutError as exc:
            raise ValueError("Historical lookup time budget exhausted; configure a healthy archival provider") from exc

    async def _first_block_at(self, timestamp_seconds):
        target = timestamp_seconds * 1_000_000_000
        latest = await self.block()
        if int(latest["timestamp_nanosec"]) < target:
            raise ValueError("Selection target is not finalized")
        # Binary search actual finalized chain. Missing-height lookup follows prev_hash;
        # a bounded forward probe handles skipped heights without substituting latest.
        async def at_or_after(height):
            for probe in range(height, min(height+8, latest["height"]+1)):
                try:
                    return await self.block(probe)
                except MissingBlock:
                    continue
            raise ValueError("Missing historical block: archival provider required")
        # Bracket backwards from the tip. Recent-week replays should not query
        # years-old midpoint blocks just to locate a recent cutoff.
        high=latest["height"]
        distance=1024
        while True:
            low=max(1,latest["height"]-distance)
            earlier=await at_or_after(low)
            if int(earlier["timestamp_nanosec"])<target:break
            if low==1:raise ValueError("Selection target precedes the available chain")
            high=earlier["height"]
            distance*=2
            await asyncio.sleep(.6)
        low=earlier["height"]+1
        while low < high:
            await asyncio.sleep(.6)
            mid = (low + high)//2
            block = await at_or_after(mid)
            if int(block["timestamp_nanosec"]) < target:
                low = block["height"] + 1
            else:
                high = mid
        selected = await at_or_after(low)
        previous = await self.predecessor(selected)
        if not int(previous["timestamp_nanosec"]) < target <= int(selected["timestamp_nanosec"]):
            raise ValueError("Historical predecessor proof failed")
        return {"height": selected["height"], "hash": selected["hash"], "timestamp_ns": str(selected["timestamp_nanosec"]),
                "timestamp_seconds": int(selected["timestamp_nanosec"])//1_000_000_000,
                "previous_timestamp_ns": str(previous["timestamp_nanosec"]), "rpc_network": "mainnet", "verified": True}
