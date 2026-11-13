# Successful Explorer records: 1-8 November 2026

Count checked on 13 November 2026. This is provider-reported 1Click Explorer data with status `SUCCESS` observed at query time, not a count of all NEAR blockchain transactions or proof of status at the original Sunday freeze.

| Interval (UTC, end exclusive) | With overlap | Overlap subtracted | Successful records |
|---|---:|---:|---:|
| 1 November 00:00 - 2 November 00:00 | 16,733 | 0 | 16,733 |
| 2 November 00:00 - 5 November 00:00 | 54,693 | 0 | 54,693 |
| 5 November 00:00 - 8 November 00:00 | 58,514 | 0 | 58,514 |
| Calendar week total | | | **129,940** |
| Additional demo query interval: 8 November 00:00 - 00:17:11 | 146 | 0 | 146 |
| Full historical demo query interval | | | **130,086** |

At 1,000 successful records per page, the full demo interval has **131 data pages** according to this count. This is a SUCCESS-only denominator; it must not be compared directly with the paused collector's all-status received-row counter.

## Method

Authenticated `GET https://explorer.near-intents.org/api/v0/transactions-pages` with `page=1`, `perPage=1`, `statuses=SUCCESS`, `showTestTxs=false`, and Unix timestamp bounds. Read the response's `total` without downloading the matching records. The endpoint is absent from the main Swagger reference; its own rate-limit error says it is deprecated and allows one request per minute. Queries waited at least 62 seconds between starts. A whole-week query failed with HTTP 500, while the smaller windows above succeeded. Some previously verified matching count observations were reused and marked in the JSON audit.

For each desired interval `[start,end)`, request a one-second overlap at the start and subtract a separate count of that overlap:

```text
successful_count = total(start - 1, end) - total(start - 1, start)
```

The four resulting intervals are adjacent and cover the whole requested range. An independent arithmetic audit checked their adjacency, overlap subtraction, sums and page calculation. All four measured overlaps were zero. Raw queries, observations and timings are recorded in [the count audit](2026-11-01-success-count.json); it contains no tokens, addresses or transaction payloads.

The demo's selected block timestamp is `1794097030218994184` ns (8 November 00:17:10.218994184 UTC). Its collector uses the seconds-based query endpoint `1794097031` to cover that selected second, then checks membership using the declared `createdAtTimestamp` field. The final canonical dataset still requires capture, identity deduplication and per-record verification; this report does not certify a completed artwork.

Counts are not an atomic historical status snapshot and may change if the provider revises records. The deprecated count endpoint needs an error/rate-limit fallback before production use. The existing bulk collector was left paused throughout this count.
