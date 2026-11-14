# Architecture

One testnet application: Next.js on Vercel, a Render FastAPI service with one leased weekly worker, PostgreSQL, a persistent private source archive, and a constrained Node signer. Fresh keyless NFT, auction and marketplace contracts run on NEAR testnet. Each economic NFT maps to its own keyless vault subaccount. The separately preserved genesis is read from its original contract.

The worker commits a protocol policy before observation. At Sunday 18:00 UTC it verifies drand and the selected mainnet block/predecessor. Two complete, consistent, recent Explorer observations must finish before the fixed freeze. Only SUCCESS records in the exact nanosecond interval contribute. Missing/late/inconsistent observations stop publication. Source completeness remains provider-trusted.

PostgreSQL stores normalized observations, frozen epochs, ordered Merkle membership, accepted direction, releases, jobs, exact signed effects and indexed receipts. Content-addressed local files retain private source/scene artifacts for verification and restart recovery. Hosted API and worker share one persistent disk; canonical minted artwork never depends on those files.

The scene renderer maps transaction statistics to geometry/materials and chooses the family from the verifiable seed. NEAR AI supplies the first persisted valid styling direction. A frozen IDART1 display list is uploaded append-only, both SVG views are checked independently, then the NFT is sealed/minted into auction custody. Its dedicated account is prepared before the 24-hour auction activates. The contract owns immutable geometry, renderer, inline public provenance and media hashes.

The PostgreSQL advisory lease and durable signing journal serialize automated writes. Unknown outcomes block fresh nonce reservation; recovery checks exact signed transactions. Worker cancellation drains its child tick before releasing the lease. The signer restricts testnet, account, contract, method, gas and attached deposit. Onchain state remains authoritative for ownership, settlement, refunds and rewards; receipt history is partial unless observed/indexed.

The keeper runs settlement/refund/funding maintenance during long captures and between release windows. At UTC month end it submits collection, fixed drand proof and royalty payments under contract rules. It never chooses a beneficiary or winner using an LLM. See ECONOMY.md for the 20/80 allocation, optional early exit, rollover and 5% secondary fee.

The root uv workspace manages Python 3.12 and uv.lock. npm and Cargo retain separate locks. Hosted startup requires migrated PostgreSQL. The local viewer uses a separate SQLite database with background signing/scheduling disabled. Synthetic and historical test utilities are developer tools, not additional deployed products.
