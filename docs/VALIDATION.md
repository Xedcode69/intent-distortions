# Release validation — 2026-11-12

**Status: managed-cloud production candidate plus a separate educational demo. Live acceptance and independent security review are outstanding. No cloud resources/contracts were deployed and no real financial outcome is claimed.**

| Check | Observed result |
|---|---|
| uv workspace / Python 3.12 | Locked graph installs in root `.venv`; unused yanked NumPy dependency removed; runtime and dev dependencies separated |
| Python tests | **58 passed**, including a real local PostgreSQL 18 server; one upstream Starlette/AnyIO deprecation warning |
| PostgreSQL | Both Alembic revisions upgrade cleanly and idempotently; ORM/schema comparison clean; exclusive advisory-lock acquisition/release tested |
| Weekly worker | Offline isolated integration uses a real verified beacon with explicitly mocked Explorer/block RPC; observes twice before freeze, renders once, reuses the checkpoint and waits for signing; no mocked financial success is presented as real |
| Safety/recovery tests | Policy immutability, hidden credential errors, fixed observation cutoff/disagreement, chunked request limit, pending transaction nonce blocking/exact-byte reconciliation, write-once S3 read-back, successful-receipt-only indexing and deduplication |
| Rendering | Six distinct bounded families tested on 10,001 records; compact Merkle index produces correct odd-leaf membership paths |
| Original fixture | All file hashes, seed/Merkle/data commitments, scene/statistics reconstruction and PNG replay pass; original canonical image unchanged |
| Contracts | **22 native tests passed**: 16 auction, 6 NFT. Includes durable delivery after winner resale, lost callback reconciliation, stale custody callbacks, wrong-beneficiary rejection, treasury idempotency and historical locked curation |
| WASM | Both current contracts build with Rust 1.95 / SDK 5.30.1 for `wasm32-unknown-unknown` |
| JavaScript | **7 tests passed**: Python/browser selection, snapshot/Merkle/seed agreement, tampering/image hash checks, SDK transaction signature/signer scope, plus production proxy redirect, request-boundary and error-redaction guards |
| Frontend | Next.js 16.4.6 production build and TypeScript pass; six standalone page routes, runtime private-API proxy, security headers, blocked admin/demo paths and request size limits checked against the local demo API |
| Educational demo | Independent static HTTP/assets/security headers/image hash checks pass; no production API or `.env` is served |
| Managed deployment | `render.yaml` passes Render's official JSON schema plus local separation/retention checks. CloudFormation JSON parses; AWS-side validation/deployment still required |
| Dependency audits | npm production graphs: no high/critical findings; 11 low frontend / 4 low signer advisories remain in the SDK transitive elliptic chain; see SECURITY.md |

The original demo contains 36 synthetic records, no real swaps, no live AI response and no real NFT/auction activity. The independently packaged educational sample uses separate synthetic checkpoint evidence and artwork; rebuilding it does not mutate the frozen local edition. The only real public beacon fixture is default-network drand round 6624326, released 1794160800, verified offline. Historical public archival lookup previously encountered rate limits/timeouts; no verified block was fabricated.

Current build artifacts:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `echo_nft.wasm` | 466376 | `f4ef77b51c9fb3f6011be02b25cc78b755badfd4767b4c4fa29fcdd6f20ec361` |
| `echo_auction.wasm` | 393109 | `00a1c54e123cc11d3c9013b00935ebd6609c61434723834142e4c2e7c42f7d14` |
| Original frozen demo PNG | 168412 | `a021aabfcd50472ccced42a57a771c13cd3038b1fc93f96f4b9f617f813b360d` |

WASM files are built under ignored `contracts/target/wasm32-unknown-unknown/release/` and included in the managed-cloud candidate archive. Source and lockfiles remain authoritative. The separate ZIP deliverables have per-file SHA-256 manifests. Native test environments do not validate actual onchain gas, network execution or cross-contract receipt ordering. Rust emits upstream/test-only deprecation/unused warnings; WASM builds succeed.

The production frontend may be exercised against the local demo API for route/proxy checks. That does **not** establish production credentials, live swap coverage, actual auction state or cloud commissioning. The demo strip continues to identify that source as synthetic.

Not yet validated: Docker image execution on a working Docker host; full browser/mobile/accessibility and wallet interaction; managed cloud rollout/rollback/backup restoration; authenticated real Explorer captures and fixed freeze capacity; live paid NEAR AI generation; deployed matching contract bindings/code hashes; real mint, two bids, anti-sniping, refunds, winner ownership, settlement recovery and treasury credits; complete network-wide receipt history; independent contract/security review. Current bid indexing is deliberately partial.

Browser visual QA remains unavailable: the earlier browser host failed and automatic approval review rejected native Chrome access. Artwork PNG bytes were visually inspected directly. Docker definitions and CI build jobs are supplied, but the workstation Docker daemon was unavailable. These gaps are recorded rather than treated as successful checks.

Run commands and release gates: [README](../README.md), [managed-cloud guide](managed-cloud.md), [contract operations](CONTRACTS.md). The presence of deployment files or keys must never be substituted for live acceptance evidence.
