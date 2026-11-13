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

## Asset networks and reproducible lookup

New real-data editions use renderer `echo-renderer-3`. Before generation, the runner resolves each exact origin/destination asset ID against the public [1Click token registry](https://docs.agentsonintents.com/api-reference/oneclick/get-supported-tokens). It freezes a minimal registry snapshot (asset IDs and blockchain codes, with no changing prices), the used-asset lookup and its observation time. The mapping is included in the content-addressed provenance as `asset-networks.json` and checked during offline replay. Unlisted historical IDs remain explicitly unresolved; a token symbol or address resemblance never supplies a guessed network.

Resolved networks drive routes, palette categories, recognized-chain diversity, geometry and the AI statistics. The art seed additionally commits to the used asset-to-network assignments. Fetch time and unrelated registry additions cannot reroll that seed. Unknown source records do not count as a recognized chain or enter the recognized-chain entropy calculation; they remain included in the dataset, commitments and total swap count. The public demo shows exact asset and source/destination record coverage and the frozen mapping hash.

Existing renderer-1/2 editions retain their original mapper and seed rules for byte-identical verification. An already generated edition cannot be rewritten with a new mapping. To regenerate a historical demonstration, copy its verified capture, plan, beacon and checkpoint into a fresh directory under ignored `data/replays/`; omit its database and generated content. An optional prepared `asset-networks.json` in that directory must validate against the saved capture; otherwise a new epoch fetches and freezes the registry itself. No Explorer re-download is needed. Registry observations are current metadata, not a claim that the registry was identical at the historical freeze.

New live protocol commitments declare renderer-3, `exact-registry-asset-id-v1` mapping and the registry-bound seed policy. An existing live protocol commitment cannot silently adopt this change; use a separately prepared protocol/database migration before deployment.

## Exact historical interval

This workflow creates an **isolated first replay edition**. Its default genesis is the previous Sunday at 00:00 UTC, and its endpoint is the drand-selected checkpoint on the requested Sunday. For 8 November, the default start is 1 November 2026 00:00 UTC. Use `--start <unix-seconds>` to set an explicit earlier checkpoint. This is not automatically a reconstruction of an already-existing production edition or a Monday–Sunday calendar week.

The runner verifies the predetermined drand round, derives the target timestamp and independently checks the selected mainnet block, its predecessor and finality. It then uses the exact `[start_ns,end_ns)` interval, complete Explorer pagination and successful eligible records. An empty successful dataset fails this acceptance test rather than producing a misleading example.

New historical captures request only `SUCCESS` records from Explorer, retaining that filter and the date bounds on every cursor page. Unexpected response statuses stop the capture. The one-second lower-bound overlap is removed locally, deposit identities are deduplicated, and the final snapshot checks the exact checkpoint interval again. Unsuccessful records do not contribute to the artwork. Production status reconciliation continues to request all supported statuses.

The cursor endpoint excludes test records when `showTestTxs` is omitted. Its flag parser treats any supplied string, including `false`, as enabling test records; the deprecated pages endpoint instead parses `true`/`false` values. The collector therefore omits this flag. Do not copy the pages endpoint's `showTestTxs=false` convention into a cursor request.

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

The documented cursor endpoint returns transaction arrays without a total field. A separate, deprecated `/transactions-pages` endpoint can return filtered totals. Smaller time-window counts, with their boundary overlaps subtracted, produced an advance SUCCESS count of 130,086 for the 8 November demo interval; see the [saved count audit](reports/2026-11-01-success-count.md). Such observations are advisory: statuses can change between queries, and the deprecated endpoint can time out. The final contributing count comes from complete pagination, deduplication and exact-boundary validation of the actual capture. Public daily or rolling transaction totals may cover different records and must not be used as this run's denominator.

The historical runner writes an allowlisted `progress.json` with phase, received-row count, pages, elapsed time and the requested interval. The local historical API exposes `GET /api/v1/replay/progress`; the `/demo` page polls it every five seconds. Collection uses an indeterminate progress bar while the total is unknown, then reports the completed capture's unique record count and successful eligible count separately. The bar measures collection completion, not paid generation or verification completion. Stale updates are labelled. No provider records, URLs or credentials enter the progress response. Production mode does not expose this local progress endpoint.

The initial all-status collection was paused and then discarded at the owner's request. Its in-memory records are not used by the replacement SUCCESS-only capture. New runs publish progress directly on each received page.

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

The Demo section first plays a skippable 20-second presentation using the published aggregate statistics: successful record count, activity in 24 equal intervals, dominant routes, checkpoint and seed inputs, followed by the canonical artwork reveal. Pause, chapter selection, Next and Replay controls are available. Reduced-motion preferences disable automatic playback and decorative transitions. A waiting page polls for the verified publication so a newly prepared result can appear without a manual refresh.

After the reveal, visitors can choose **Static image**, **Animated view** or **Explore the layers**. The animated view traces light along the saved route polylines and adds slow particle pulses and geometric motion, with Play/Pause and Restart controls. It is explicitly an interpretation of the recorded scene; the canonical PNG, artwork commitments and offline verification remain fixed. The public index includes aggregate activity, chain categories, routes and reported USD coverage for the presentation, with no per-record identities. Unmapped assets are labelled as an unknown category rather than counted as an identified blockchain.

## Testnet NFT/auction acceptance

Once the historical artwork is valid, real mint/bid/settlement checks need dedicated deployed testnet contracts, funded testnet accounts and publicly accessible immutable artifact URLs. The existing `scripts/testnet_lifecycle.py --edition historical_replay-000001 ...` can use that database when the corresponding replay profile and separate testnet contract settings are explicitly configured. Its compressed auction exercise must use dedicated demonstration contracts. The read-only preview profile intentionally does not include any contract IDs or signing credentials.

Every isolated run uses replay epoch 1. Do not mint different replay runs into the same NFT contract's epoch namespace; use dedicated test contracts or the separately managed consecutive replay workflow. Do not interpret a successful historical art test as a successful real auction or full production certification.
