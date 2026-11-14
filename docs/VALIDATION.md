# Current validation — 14 November 2026

This is the single **testnet** prototype. Earlier reports describe earlier builds/rehearsals and do not establish deployment of these fresh accounts.

| Check | Observed result |
| --- | --- |
| Python regression suite | 238 passed, 1 skipped. The dedicated PostgreSQL integration service was unavailable; one upstream Starlette/AnyIO deprecation warning remains. |
| Rust workspace library tests | 79 passed across auction, marketplace, NFT, vault and preserved onchain renderer. Includes staged freeze/remint rejection and transfer/payout financial cases. |
| Signer and frontend JavaScript | 34 passed. The removed standalone demo's tests are no longer a separate product gate. |
| Frontend | TypeScript and optimized Next.js build passed. Local homepage and 20 linked assets returned HTTP 200. Browser visual/wallet acceptance was not repeated for this change. |
| Source renderer/provenance | Isolated synthetic scene/statistics derivation and exact PNG replay passed. |
| Build/deployment files | Real-clock testnet WASM built; no lab clock exports. Render Blueprint validates against its cached official schema; one API/worker service shares its persistent disk. Vercel config passes. One source/WASM release bundle is generated with an allowlisted manifest. |
| Fresh public deployment | NFT, auction and market deployed to weekly-*.id-operator.testnet. FINAL receipts, exact code pins, bindings, November 15 auction rule and absent access keys verified. Public receipts/hashes: deploy/testnet.json. |
| Online dependencies | Testnet contracts, mainnet archival source RPC, preserved genesis, date-bounded Explorer authentication and configured NEAR AI model catalog passed. An unbounded Explorer health query returned HTTP 500; the corrected bounded query matches the collector. No AI generation was requested. |
| Genesis preservation | Original account/token retained. Recovered static SVG: 447,889 bytes, SHA-256 b870866d3f2eded46854edaf3f941ddd8f8bdf3d820ca5a413aa253893b2424b. Animated: 634,013 bytes, SHA-256 4689ad3685cbd2a9a2a207e004421d92bc56803b66f687b8d70c0dbb8881cbda. Both matched the existing sealed hashes. |

Still pending: first scheduled weekly end-to-end publication/auction on the fresh collection; fresh financial/wallet browser acceptance; full updated Linux Sandbox lifecycle; Docker image build (local Docker daemon stopped); managed-host deployment, mounted signer/worker activation and recovery drills. The original immutable renderer has not been changed. Older financial test balances were not moved.

The operator has about 1.1976 test NEAR after setup. A dedicated wallet currently requires about 1.47137 test NEAR before artwork storage/gas, so fund the operator further before the first drop. This reports actual storage requirements, not an arbitrary configured balance threshold.
