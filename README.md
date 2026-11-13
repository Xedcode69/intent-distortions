# NEAR ECHOES — The Weekly Genesis

Weekly generative art derived from a committed NEAR Intents dataset, a scheduled drand beacon, a verified historical NEAR block, and the previous artwork hash.

The edition economy uses dedicated keyless NEAR accounts named `monthYEAR-edition-N.<nft-account>`, with monthly numbering. November 15/22/29, 2026 go to the creator; December 6 starts 24-hour auctions. Successful sales allocate 20% to treasury and 80% to the edition account. A one-time withdrawal pays 40% of that original allocation, excludes the edition from its funded draw and rolls the remainder forward. Monthly winners use contract-verified drand proofs. See [financial rules, building and deployment](docs/ECONOMY.md). `/economy` exposes contract state; `/demo` includes a separate simulated accounting explanation. This remains a release candidate pending credentialed testnet acceptance and independent review.

The repository now contains **two separate applications**:

| Application | Purpose | Runtime |
|---|---|---|
| Production application | Authenticated ingestion, fixed freeze orchestration, recorded NEAR AI direction, deterministic art, NFT publication, auctions and recovery | Next.js + private FastAPI + one background worker + managed PostgreSQL + S3/CloudFront |
| Historical Demo section (`/demo`) | Show a completed real-data replay, its recorded layers and integrity evidence | Static allowlisted assets served by the main Next.js site; unavailable until a real replay passes and is prepared |
| [Educational demo](demo/README.md) | Explain records → checkpoint → DNA → artwork → auction → verification using synthetic data | Static HTML/CSS/JavaScript; no API, accounts, credentials or wallet |

**Release status: production candidate, pending live acceptance.** The code builds and local tests pass. No cloud resources or contracts have been deployed. No real Explorer swap capture, paid AI generation, real mint, bids or settlement have been executed. Mainnet readiness requires recorded testnet acceptance and independent contract/security review. See [current validation evidence](docs/VALIDATION.md) and [managed deployment guide](docs/managed-cloud.md).

## Start the educational demo

```powershell
uv sync --locked
uv run --locked python scripts/serve_demo.py
```

Open **http://127.0.0.1:3001**. It includes a six-step walkthrough, mathematical layer toggles, illustrative auction credits, independent browser hash checks, and a tampering example. All sample transactions, randomness and block evidence are explicitly synthetic. No confidential swap contents are accessed.

Alternatively, `docker compose up --build` serves this same isolated demo. `node scripts/package-demo.mjs` creates a static hosting directory at `dist/demo`. The committed demo assets are ready to serve; rebuilding them with `uv run --locked python scripts/build_explainer.py` never changes the application database or the original frozen fixture edition.

## Run the optional local application lab

The full application can still be explored without credentials in a separate development profile:

```powershell
uv sync --locked
# Copy only if .env does not already exist; preserve your existing configuration.
Copy-Item .env.demo.example .env
cd frontend
npm ci
cd ..
uv run --locked python scripts/dev.py
```

Open **http://127.0.0.1:3000**; API docs are at **http://127.0.0.1:8000/docs**. This profile uses SQLite, an explicitly labeled synthetic fixture and deterministic creative fallback. It has no real mint or auction. It is distinct from the static explanatory demo.

Python uses **uv exclusively**, Python 3.12 and the root `.venv`; use `uv add --package near-echoes ...` for backend dependencies and `uv add --dev ...` for tools. JavaScript uses Node.js 22 and npm lockfiles. Contracts use Rust 1.95 and Cargo.lock.

## Managed production deployment

[render.yaml](render.yaml) defines a public frontend, private API, one background worker, managed PostgreSQL 18, and an independent static demo. [The storage template](deploy/artifacts.cloudformation.json) defines private, versioned S3 with Object Lock and CloudFront distribution. Deployment is manual; previews and automatic deploys are disabled.

Follow [docs/managed-cloud.md](docs/managed-cloud.md) for environment variables, least-privilege credentials, contract initialization, migration order, preflight, operational recovery and release gates. Start from [.env.production.example](.env.production.example). Production rejects demo mode, SQLite, local storage, AI fallback and incomplete signing configuration.

Credentials are needed for Explorer, NEAR AI, durable storage and signed publication. The frontend receives only the private API address; the static demo receives none. Chain writes are disabled by default. No credentials have been configured in this workspace.

After building WASM, `uv run --locked python scripts/build_release.py` creates `dist/near-echoes-managed-cloud.zip` and `dist/near-echoes-demo.zip` with per-file hash manifests. The managed source bundle has a production-only Blueprint; the demo is packaged independently. These are candidate deliverables, not evidence of a deployed or audited service.

## Verification

To test real records from a previous week, follow [the historical testing workflow](docs/HISTORICAL_TESTING.md). Start with `uv run --locked python scripts/test_historical_week.py --sunday 2026-11-08 --check`; a real capture requires the Explorer JWT and historical RPC access. The runner isolates state, verifies/replays the artwork and writes a stage-by-stage report without signing transactions.

After that test passes, `uv run --locked python scripts/publish_replay_demo.py <report.json>` prepares the main site's separate `/demo` section from the actual artwork and aggregate evidence. Visitors need no credentials. The publisher verifies the frozen result and excludes raw captures, per-record snapshots, provider URLs and credentials; it does not deploy. The page labels fallback versus real NEAR AI direction and never treats the replay as a completed NFT auction.

```powershell
uv run --locked pytest backend/tests -q
uv run --locked python scripts/verify_epoch.py
uv run --locked python scripts/validate_deployment.py
node --test demo/core.test.mjs signer/signer.test.mjs
node --experimental-strip-types --test frontend/tests/proxy.test.mjs
cd frontend
npm run build
cd ..
cargo +1.95.0 test --locked --manifest-path contracts/Cargo.toml --workspace
cargo +1.95.0 build --locked --release --target wasm32-unknown-unknown --manifest-path contracts/Cargo.toml
```

Run `npm ci` in `signer` before signer tests. PostgreSQL migration/lease tests additionally use an explicitly supplied disposable `ECHOES_PG_TEST_URL`; they never use the normal application database. CI runs those tests against PostgreSQL and builds all three containers. Docker image builds and browser interaction still require validation on an available build/browser host.

## Evidence and trust

The live worker commits a protocol policy before collection, checks the predetermined beacon and first finalized block at the chosen timestamp, then seals only consistent observations completed before the fixed freeze. Late or inconsistent data delays the edition; it never substitutes a newer block or dataset. The provider does not expose a cryptographic historical status oracle, so this is an **observation-before-freeze policy**, not proof of the provider's exact internal state at that instant.

Merkle proofs establish membership in the published snapshot; they do not prove completeness of Explorer data. Authorized Explorer records can describe confidentially settled swaps, but the application cannot decrypt private-shard activity. Shield/unshield hashes are not treated as additional swaps. The present fixtures and educational demo contain **zero real confidential swaps**.

The renderer has six distinct mathematical families, bounded particle/route geometry, seeded substreams and an edition signature. The first valid AI direction is persisted, so replay uses recorded direction and exact scene primitives. The NFT rejects repeated epoch/image hashes. These properties provide reproducibility and practical uniqueness; they do not guarantee that every pair of images is perceptually dissimilar.

Renderer-3 introduced an exact asset-ID lookup from the public token registry. The registry snapshot and network assignments are frozen with provenance, drive network routes and visual statistics, and bind the art seed. Unresolved historical assets stay explicitly unknown, with coverage shown in the demo. Previously frozen renderer-1/2 editions keep their original lookup and seed rules. See the [registry-aware demo report](docs/reports/2026-11-08-network-mapping.md).

Current mapped editions use [renderer-4](docs/RENDERER_V4.md): a verifiable seed draw selects the family, and AI styles that fixed family. Frozen flow, community, timing and trade-size measurements drive expanded geometry, filled surfaces, ribbons, curves, materials and animation. Renderer-3 retains its original verification path. Demo and artwork views expose the recorded layers and controls; live deployment requires a new protocol commitment.

Onchain views are authoritative for ownership, highest bids and treasury balances. The receipt index contains finalized receipts observed by the worker or submitted by the first-party wallet flow; historical bid coverage is explicitly partial. Contracts store commitments and do not verify drand onchain. Worker signing does not authorize treasury withdrawals.

Read [contract operations](docs/CONTRACTS.md), [algorithms](docs/ALGORITHMS.md), [provenance](docs/PROVENANCE.md), [privacy](docs/PRIVACY.md), [security](docs/SECURITY.md) and [API](docs/API.md).

MIT-licensed software. NFT ownership does not itself grant copyright or exclusive commercial rights.
