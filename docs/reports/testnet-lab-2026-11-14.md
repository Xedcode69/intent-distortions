# Testnet lab preparation — 14 November 2026

The full application can run in an isolated testnet profile, with wallet actions
on the existing auction, marketplace, collection and rewards pages. The source
historical genesis is copied read-only and its provenance stays historical.
Five distinct synthetic editions provide December/January financial scenarios.
No transaction has been signed, and no public testnet deployment is claimed.

The lab contract feature adds an operator-controlled monotonic clock to NFT,
auction and market builds and fixes monthly entropy to verified historical
drand round 6624326. Production builds expose neither lab initializer nor clock
setter, as checked against the compiled binaries. The keyless vault needs no
clock and its WASM is identical in both builds. HTTP processes have no signer
credentials. CLI operator writes are explicit, journaled and reconciled against
finalized onchain state; the site pauses lab wallet actions when clocks differ.

| Validation | Result |
| --- | --- |
| Backend regression | 169 passed, 1 PostgreSQL test skipped; existing AnyIO deprecation |
| Focused final changes | 40 tests passed across rehearsal, lab, drops and marketplace; final CLI/recovery/deployment-plan checks: 5 passed |
| Contract tests | Production 62 passed; lab 71 passed |
| Frontend / Node | Production build and TypeScript passed; 19 Node tests passed |
| Frozen original fixture | `scripts/verify_epoch.py` passed |
| Actual local lab | Eight routes returned HTTP 200; six distinct artworks; testnet health; wallet actions paused with blank accounts |
| Data isolation | Historical source database hash unchanged; canonical PNG remains `8fec6c77137badb4cd124b8235287eb36ab902ebbb0f27e6b78829dd47af8fca`; public export allowlist excludes snapshots/raw captures |
| Public testnet | Not run: accounts and CLI keychain authorization not configured |
| Sandbox rerun | Not run: Docker daemon stopped; prior lifecycle evidence remains historical |
| Browser wallets / managed cloud | Not exercised in this change |

Current SHA-256 pins (WASM is ignored and packaged separately):

| Contract | Production | Testnet lab |
| --- | --- | --- |
| NFT | `da9b137928cda167cb888582995e33dc517f90ae54478db5673db9ccc3527a0d` | `68b1cbf9ae9e55ca5c2e1e7dc4d0464935c68ea0d121945e8662d40d948130fc` |
| Auction | `a4aa17b23f68570ad3f85de73cfc511eb85d77fd0318fa87b5d9151a5d2af0a0` | `558861cb760680689e9780ae88ed7c828a8b9547a57406785f7f058fd6d6aeb1` |
| Marketplace | `950995aff438c904deda2cace1cfbf817d61dfa95122888bc112c1c01ee4ab6e` | `429ed11bca96eddc0883063c272b7c4a598fcf5bd135b3b03cea7a5402811703` |
| Vault | `0bd2832599944647bcf6d019600409d1e709efe9eb4a1e24d0641c943af9b2f1` | Same |

The testnet clock, known historical entropy and synthetic editions are rehearsal
tools, not production randomness or later weeks' real data. Live 1Click funding
remains mainnet-only; native testnet trading covers settlement paths, while an
actual cross-chain deposit requires separate mainnet acceptance.

See [the complete setup and financial acceptance runbook](../TESTNET_LAB.md).
