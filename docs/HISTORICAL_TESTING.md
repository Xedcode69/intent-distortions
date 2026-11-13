# Test a previous week's data

Historical replay exercises the actual collection, checkpoint verification, canonical dataset, Merkle tree, seed, creative direction, renderer and artifact-verification code. It uses its own database and storage, keeps raw captures private, and never signs transactions. The explanatory static demo remains separate.

## Current prerequisite

A real Explorer capture needs an accepted `NEAR_INTENTS_PARTNER_JWT` with **Explorer** key type from the partner console. A Distribution Channel/1Click key is not the Explorer credential. A working mainnet RPC with access to the chosen historical blocks is also needed. The public archival endpoint is severely rate limited; a failed lookup is reported rather than replaced with a fabricated or recent block.

Create an ignored replay configuration without changing `.env`:

```powershell
uv sync --locked
Copy-Item .env.replay.example .env.replay
$env:ECHOES_ENV_FILE = '.env.replay'
```

Edit `.env.replay` locally. Set the Explorer JWT and, if needed, a healthy `NEAR_MAINNET_RPC_URL`. Never paste secret values into chat or commit them. The API documentation describes JWT authentication and full pagination: [Explorer transactions](https://docs.near-intents.org/api-reference/get-transactions). Choose an archival provider using the [NEAR provider reference](https://docs.near.org/api/rpc/providers).

| Environment setting | Needed now? | Purpose |
|---|---|---|
| `NEAR_INTENTS_PARTNER_JWT` | Required for a new real capture | Authenticated Explorer pagination |
| `NEAR_MAINNET_RPC_URL` | Required working endpoint | Historical mainnet block, predecessor and finality queries; include a provider API key in the URL only if that provider requires it |
| `NEAR_AI_API_KEY` | Only with `--ai required` | Funded NEAR AI Cloud access |
| `NEAR_AI_TEXT_MODEL` | Only with `--ai required` | Available model ID for that account |

The template already supplies the Explorer/AI base URLs and disables chain writes. Historical artwork testing needs no wallet private key, funded NEAR account, NFT/auction contract, AWS/S3 credentials, database password or admin token. A prepared public demo needs none of the above credentials at viewing time.

Keep values in ignored `.env.replay`, not the tracked `.env.replay.example`. `--check` verifies presence only; provider acceptance is established by the actual run. Copy the AI model ID exactly from the account's model catalog. Providers that support historical height lookup but cannot resolve a parent hash are handled by fetching a numeric candidate and requiring its hash to equal the selected block's exact `prev_hash`; an unlinked candidate is rejected.

## Run the test

From the repository root:

```powershell
# Local readiness only: does not contact providers.
uv run --locked python scripts/test_historical_week.py --sunday 2026-11-08 --check

# Optional: verify the public beacon and historical checkpoint before obtaining a JWT.
uv run --locked python scripts/test_historical_week.py --sunday 2026-11-08 --prepare

# Fetch a complete real capture, render, verify and export the historical artwork.
uv run --locked python scripts/test_historical_week.py --sunday 2026-11-08
```

Omit `--sunday` to choose the latest Sunday whose 18:00 UTC beacon has been released. The default AI policy is explicitly `fallback`, which tests the mathematical pipeline without making a paid AI request. To include real NEAR AI direction, configure a funded key and current model ID, then run:

```powershell
uv run --locked python scripts/test_historical_week.py --sunday 2026-11-08 --ai required
```

The `required` policy refuses missing/failed AI and never silently falls back. Its output directory is separate from the fallback run. Each directory pins the requested date and starting checkpoint. The AI model can be configured after readiness/public preparation and is pinned once generation initializes its database; use a separate directory for later model changes. Only one collector should use a partner JWT at a time.

## Exact historical interval

This workflow creates an **isolated first replay edition**. Its default genesis is the previous Sunday at 00:00 UTC, and its endpoint is the drand-selected checkpoint on the requested Sunday. For 8 November, the default start is 1 November 2026 00:00 UTC. Use `--start <unix-seconds>` to set an explicit earlier checkpoint. This is not automatically a reconstruction of an already-existing production edition or a Monday–Sunday calendar week.

The runner verifies the predetermined drand round, derives the target timestamp and independently checks the selected mainnet block, its predecessor and finality. It then uses the exact `[start_ns,end_ns)` interval, complete Explorer pagination and successful eligible records. An empty successful dataset fails this acceptance test rather than producing a misleading example.

Historical status is observed **when we capture it now**. Without a capture recorded at the old freeze, the test cannot establish which records were successful at that past instant. It does not test a real-time Sunday observation window, contract deployment, NFT minting, bidding or treasury payment. Those remain separate live/testnet acceptance exercises.

## Outputs and pass criteria

Outputs are under ignored `data/replays/<Sunday>-from-<start>-<AI-policy>/`:

| File | Meaning |
|---|---|
| `readiness.json` | Local missing requirements, without secret values |
| `plan.json` | Pinned historical test inputs and status-observation policy |
| `beacon.json`, `evidence.json` | Checked public randomness and checkpoint evidence |
| `capture.raw.json` | Private raw provider records; never publish this file |
| `capture.source.json`, `capture.snapshot.json` | Capture metadata, hashes and redacted canonical records |
| `replay.db`, `content/` | Isolated test state and content-addressed artifacts |
| `report.json`, `report.md` | Explicit passed/blocked/failed stages and test scope |
| `export/artwork.png`, SVG, WebP and JSON files | Actual generated artwork, scene, dataset commitments and provenance |
| `preview.env` | Credential-free local serving profile |

A successful mathematical test checks complete capture integrity, exact membership, Merkle proofs, seed derivation, statistics and scene reconstruction, exact PNG replay, identical results on repeat invocation, and rejection of altered records/commitments. Tampering checks use copies and leave the frozen artwork intact. It confirms no NFT or auction was created.

Saved captures are hash-checked and reused on subsequent runs, avoiding repeated Explorer requests. The mainnet checkpoint is rechecked online. Tampered or changed inputs fail; frozen state is not reset. Provider failures and missing credentials produce a report with an explicit blocker/error type and no fabricated successful stage. An OS-owned workspace replay lock prevents concurrent invocations of this runner; do not share the partner JWT with another collector process while testing.

## View the generated result

After the report says `passed`, use the exact report path printed by the runner:

```powershell
uv run --locked python scripts/serve_replay.py data/replays/2026-11-08-from-1793491200-fallback/report.json
```

Open **http://127.0.0.1:3003**. The replay API uses **127.0.0.1:8001**. The launcher rejects occupied ports; `--web-port` and `--api-port` can override them. It uses a dedicated `.next-replay` build directory, sanitizes inherited credentials, disables signing/scheduling, and stops its own two processes on Ctrl+C. It does not alter the existing demo or production configuration.

The UI labels historical replay as read-only, disables wallet actions and displays the recorded block. The DNA viewer and provenance checks use the generated edition's actual manifest. You can also inspect `export/artwork.png` and the reports directly without starting servers.

### Collection progress and the weekly count

The official Explorer OpenAPI specification documents paginated transaction arrays, not a filtered total-count endpoint or a total field in the response. An exact count for this run is therefore established by completing the same pagination, deduplication and exact-boundary filtering used for the artwork. Public daily or rolling transaction totals may cover different records and must not be used as this run's denominator.

The historical runner writes an allowlisted `progress.json` with phase, received-row count, pages, elapsed time and the requested interval. The local historical API exposes `GET /api/v1/replay/progress`; the `/demo` page polls it every five seconds. Collection uses an indeterminate progress bar while the total is unknown, then reports the completed capture's unique record count and successful eligible count separately. The bar measures collection completion, not paid generation or verification completion. Stale updates are labelled. No provider records, URLs or credentials enter the progress response. Production mode does not expose this local progress endpoint.

The already-running first real capture was started before native progress-file reporting was added; its observed CLI counters are relayed to the local display without restarting or discarding the in-flight collection. Subsequent runs publish progress directly on each received page.

## Prepare the site's separate Demo section

The main site's **Demo** navigation item opens `/demo`. It reads a static, verified historical presentation independently of the production API/database. Before a real run is published, it explicitly says that no completed historical demo is available. It never presents the synthetic educational sample as real history.

After a historical test passes:

```powershell
uv run --locked python scripts/publish_replay_demo.py data/replays/2026-11-08-from-1793491200-fallback/report.json
```

This rechecks the original capture, scheduled beacon, saved checkpoint consistency, full scene/PNG reconstruction and recorded acceptance assertions. It writes an allowlisted bundle to `frontend/public/historical-demo/`: the canonical image, scene primitives and a presentation index with aggregate counts, dates, commitments, direction provider and verification results. It does not re-query the archival RPC during publication; the saved checkpoint was independently checked during replay.

The bundle excludes raw provider records, the canonical per-record snapshot, credentials, environment files, provider URLs, database files and full source metadata. Failed, incomplete or altered runs cannot replace the current presentation. Browser checks independently hash the image and scene; full dataset verification remains an offline runner check, labelled accordingly.

Open `/demo` in the existing frontend or read-only replay preview. If its dev server was already running when the first bundle was prepared, restart that frontend so Next.js discovers the new public files. For hosting, include the prepared public assets in the deployment checkout, rebuild the frontend and deploy through the normal approved release process. The publisher prepares local files only and never deploys. The Docker runtime copies `public/` alongside the standalone server. The prepared allowlisted public assets can be committed; private files under `data/replays/` remain ignored.

Visitors can inspect the artwork, toggle recorded layers, follow the actual run's mechanics and verify file commitments without a wallet or API key. A fallback run is still real data and real generated art, with deterministic fallback direction labelled explicitly; only a successful `--ai required` run demonstrates paid NEAR AI generation. The separate synthetic educational app remains available for an explanation before credentials are configured.

## Testnet NFT/auction acceptance

Once the historical artwork is valid, real mint/bid/settlement checks need dedicated deployed testnet contracts, funded testnet accounts and publicly accessible immutable artifact URLs. The existing `scripts/testnet_lifecycle.py --edition historical_replay-000001 ...` can use that database when the corresponding replay profile and separate testnet contract settings are explicitly configured. Its compressed auction exercise must use dedicated demonstration contracts. The read-only preview profile intentionally does not include any contract IDs or signing credentials.

Every isolated run uses replay epoch 1. Do not mint different replay runs into the same NFT contract's epoch namespace; use dedicated test contracts or the separately managed consecutive replay workflow. Do not interpret a successful historical art test as a successful real auction or full production certification.
