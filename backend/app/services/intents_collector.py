import asyncio
import time
import httpx
from .canonical_data import normalize, record_key

class Collector:
    """Use one collector process per partner JWT (partner-wide rate limit)."""
    def __init__(self, base_url, jwt, client=None, sleep=asyncio.sleep):
        if not jwt:
            raise ValueError("NEAR_INTENTS_PARTNER_JWT is required for live ingestion")
        self.base_url, self.jwt, self.client = base_url, jwt, client
        self.sleep, self.last_request = sleep, 0.0

    async def request(self, client, params):
        for attempt in range(5):
            await self.sleep(max(0, 5 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                r = await client.get(self.base_url + "/transactions", params=params,
                                     headers={"Authorization": f"Bearer {self.jwt}"})
                if r.status_code == 429 or r.status_code >= 500:
                    await self.sleep(max(5*2**attempt, float(r.headers.get("Retry-After", 0))))
                    continue
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, list):
                    raise ValueError("Explorer response must be an array")
                return data
            except httpx.TransportError:
                if attempt == 4:
                    raise
                await self.sleep(5*2**attempt)
        raise ValueError("Explorer retry budget exhausted; epoch remains pending")

    async def collect(self, start, end, page_size=1000, on_page=None):
        if not 1 <= page_size <= 1000:
            raise ValueError("Invalid Explorer page size")
        # API start is NON-inclusive: overlap one second and filter exactly locally.
        params = {"numberOfTransactions": page_size, "direction": "next", "statuses": "SUCCESS,PROCESSING,PENDING_DEPOSIT,INCOMPLETE_DEPOSIT,FAILED,REFUNDED",
                  "showTestTxs": "false", "startTimestampUnix": start-1, "endTimestampUnix": end}
        base_query=params.copy()
        seen_cursors, records = set(), {}
        async with httpx.AsyncClient(timeout=30) as owned:
            client = self.client or owned
            for _ in range(100_000):
                page = await self.request(client, params)
                for raw in page:
                    rec = normalize(raw)  # malformed or ambiguous records prevent sealing
                    if start <= rec["created_at_unix"] < end:
                        key = record_key(raw)
                        if key in records and records[key] != raw:
                            raise ValueError("Inconsistent snapshot page; reconcile before freeze")
                        records[key] = raw
                if on_page:
                    on_page(page)
                if len(page) < page_size:
                    return list(records.values()), {"complete": True, "query": base_query,
                                                   "source": self.base_url, "pages": len(seen_cursors)+1}
                last = page[-1]
                cursor = (last["depositAddress"], last.get("depositMemo"))
                if cursor in seen_cursors:
                    raise ValueError("Pagination stalled; completeness cannot be established")
                seen_cursors.add(cursor)
                params["lastDepositAddress"] = cursor[0]
                if cursor[1] is not None:
                    params["lastDepositMemo"] = cursor[1]
                else:
                    params.pop("lastDepositMemo", None)
        raise ValueError("Page budget exhausted")
