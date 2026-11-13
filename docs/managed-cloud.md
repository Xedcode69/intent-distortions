# Managed-cloud deployment and operations

The deployment target is **Render managed compute/PostgreSQL plus AWS S3/CloudFront**. The static educational demo is a different service and can be hosted independently. These templates have not been deployed from this workspace. Current status and remaining acceptance evidence are recorded in [VALIDATION.md](VALIDATION.md).

## Services and data boundaries

| Service | Access | Persistent state / credentials |
|---|---|---|
| `near-echoes-web` | Public HTTPS | Private API host/port only; no signing, AI, Explorer or AWS secrets |
| `near-echoes-api` | Render private network | PostgreSQL and read-only artifact credential; admin token |
| `near-echoes-worker` | No incoming traffic | PostgreSQL, write-once artifact credential, Explorer JWT, AI key, optional mounted signing file |
| `near-echoes-db` | Private network only | Managed PostgreSQL 18; snapshots, releases, observations, effects, receipt index |
| `near-echoes-explainer` | Separate static URL | Synthetic public teaching assets only; no environment group |
| S3 / CloudFront | Bucket private; redacted artifacts public through CDN | SHA-256 keys, versioning, Object Lock, HTTPS |

The frontend resolves `BACKEND_URL` at runtime through a bounded streaming API route, so the same image works with Render service discovery. It sends the canonical internal Host `echoes-api.internal`, which the API explicitly allows. The proxy rejects demo and admin paths in production and forwards no authorization header. Administrative requests must use a trusted private-network shell/port-forward with the internal Host and bearer token. Public verification/receipt requests have body/rate limits; forwarded client-IP headers are not trusted. Add provider edge rate limits before scaling public traffic.

The API has no scheduler in production and does not create tables at startup. A single background worker holds a session-level PostgreSQL advisory lock and probes ownership while work runs. Use the direct database connection string, **not a transaction-pooling connection**, for this worker. Do not share one partner JWT across additional collectors or run two independent databases with the same signer account. Worker deployments should stop the old instance before replacement; the advisory lock rejects overlapping instances.

## Configuration and credentials

Copy `.env.production.example` to an ignored operator file, or set the equivalent service variables in Render. For local operator commands:

```powershell
$env:ECHOES_ENV_FILE = '.env.production'
uv sync --locked
uv run --locked python scripts/production_preflight.py
```

| Value | Where needed | How to obtain / purpose |
|---|---|---|
| `DATABASE_URL` | API / worker | Render private direct connection string; `postgresql://` is normalized to psycopg |
| `ADMIN_TOKEN` | API / worker group | Generated random token of at least 32 characters; never send to frontend |
| `NEAR_INTENTS_PARTNER_JWT` | Worker only | Authorized NEAR Intents partner Explorer access |
| `NEAR_AI_API_KEY`, `NEAR_AI_TEXT_MODEL` | Worker key; model ID shared policy | Funded NEAR AI Cloud account; ID must exist in its live model catalog |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Separate API / worker credentials | Attach ReaderPolicy to API identity and WriterPolicy to worker identity; no delete permissions |
| `SIGNER_KEY_FILE` | Worker only when writes enabled | Render secret file `/etc/secrets/near-worker.json`; NEAR CLI JSON with `account_id`, `public_key`, `private_key` |
| `NEAR_MINTER_ACCOUNT` | Shared binding | Dedicated funded operator account matching NFT minter and auction owner |
| `NEAR_NFT_CONTRACT`, `NEAR_AUCTION_CONTRACT` | Shared / public IDs | Separate deployed contract accounts on `NEAR_NETWORK` |
| `EXPECTED_NFT_CODE_HASH`, `EXPECTED_AUCTION_CODE_HASH` | Shared immutable policy | Lowercase SHA-256 of independently reviewed WASM bytes; checked against deployed code |
| `NEAR_RPC_URL` | API / worker | Healthy finality-capable RPC for the contract network |
| `NEAR_MAINNET_RPC_URL` | Worker | Archival mainnet RPC for the selected historical source block, even when contracts are on testnet |
| `S3_BUCKET`, `S3_REGION`, `ARTIFACT_PUBLIC_URL` | API / worker | Storage stack outputs; public URL is CloudFront HTTPS origin without `/sha256` suffix |
| `PROTOCOL_ID`, `FIRST_RELEASE_SUNDAY`, `GENESIS_CHECKPOINT` | Shared immutable policy | Distinct protocol ID, a future Sunday, and earlier Unix-seconds checkpoint |
| `PUBLIC_ORIGIN`, `CORS_ORIGIN` | Shared | Exact production frontend HTTPS origin |

Secrets are not included in Docker build context or static packages. Render secret-file contents must be supplied through its dashboard/secret management; never paste a private key into YAML, shell arguments, logs or source. The isolated Node signer reads the file via stdin request, enforces contract/method/gas/deposit limits and never prints the key. The worker still holds an account key at the operating-system trust boundary. Use a dedicated, minimally funded signer account; it must not control treasury withdrawals or contract-upgrade credentials. Deposits require a suitable funded account key; do not assume a NEAR function-call access key can attach deposits.

Production sets `APP_ENV=production`, `EXECUTION_MODE=live`, `STORAGE_PROVIDER=s3`, `ALLOW_AI_FALLBACK=false`. `ENABLE_CHAIN_WRITES=false` is the default. Mainnet additionally requires the explicit owner-authorized `MAINNET_WRITES_APPROVED=true` setting; this repository does not grant that authorization.

## Deploy in this order

1. Review source, run CI, build and archive WASM/container hashes. Validate `render.yaml` with `uv run --locked python scripts/validate_deployment.py`. The committed Render schema was downloaded from the official endpoint; refresh deliberately with `--refresh-schema` when updating provider configuration. AWS resource semantics still need `aws cloudformation validate-template` and an inspected change set in the intended account.
2. Create the artifact stack from `deploy/artifacts.cloudformation.json` in the chosen AWS account/region. It creates a private bucket, CloudFront OAC, and managed IAM policies; it creates no users or access keys. The bucket and objects are retained on stack deletion. **COMPLIANCE retention is ten years** and prevents deletion of retained versions; choose and approve the retention policy before creating the stack. Bucket policy requires conditional `If-None-Match` writes to content-addressed keys. Public access through CloudFront is limited to `sha256/*` redacted artifacts.
3. Initialize fresh testnet NFT with **`new_production`**, binding the auction account. Initialize auction `new` with `demo_duration_seconds:null`, separate treasury accounts, `[6000,2500,1500]`, and the reviewed reserve/increment. See [CONTRACTS.md](CONTRACTS.md). Compressed demonstration contracts are rejected by production preflight. Contract upgrade authority is a separate governance/security decision; signing-process checks do not prevent an external administrator upgrading contract code.
4. Import `render.yaml` from the repository. Fill all `sync:false` settings and configure the worker secret file. Keep API and worker storage credentials separate. The API pre-deploy command runs `alembic upgrade head`; let it finish before starting/restarting the worker. A first parallel Blueprint deployment may restart the worker until migrations exist. The API and worker must use the same complete protocol policy before either starts.
5. From the private worker environment run `uv run --locked python scripts/production_preflight.py --online` (containers may use `/app/.venv/bin/python` directly). This reads migration state, contract network/bindings/rules/code hashes, bucket protections, Explorer authentication and the AI catalog. It does not sign, generate art or prove the entire pipeline. Do not run this probe concurrently with the collector: Explorer pacing is partner-wide.
6. With writes still disabled, start well before the first fixed observation window. Verify index progress, beacon/block evidence and at least two consistent complete observations. A missed initial freeze cannot be backfilled as if it had happened on time; commission a new future protocol before publishing any edition.
7. Complete the acceptance evidence below. Enable signing only on the approved testnet deployment, then separately commission mainnet after independent review. Bind the public domain and test the CDN, wallets, empty states and mobile interaction. The explanatory static site can be deployed separately at any point without production credentials.

The Docker image uses uv 0.9.22 with `uv sync --locked --no-dev --no-editable`; it contains the official NEAR transaction SDK signer, migrations and operational scripts. Fixtures are excluded. API and worker are non-root. The static demo can also use its own non-root nginx image. Container tags are build inputs, so archive the resolved image digests for each reviewed release.

## Fixed weekly release policy

The published protocol commitment includes the first Sunday, genesis checkpoint, network/accounts/code hashes, scheduled beacon chain, renderer/model IDs, observation age and reconciliation delay. Once committed to a database it cannot be silently changed. Use a new protocol/database for an intentional policy change and document its lineage. Never copy the local demo database into production.

At Sunday 18:00 UTC the predetermined drand round is BLS-verified. Rejection sampling selects a timestamp within Sunday `[00:00,17:00)`; archival RPC verifies the first finalized block at or after it and its predecessor. Full Explorer scans use the consecutive checkpoint interval `[start_ns,end_ns)`, include only successful eligible records and preserve exact decimal strings.

Before the fixed freeze, each complete scan stores a redacted immutable snapshot and observation completion time. Sealing requires the **latest two** complete observations in the published age window to agree; an older preferred snapshot cannot bypass a newer disagreement. A scan completed after freeze is ineligible. Incomplete pagination, missing randomness/block evidence, disagreement or missing observations leaves a delayed release with no substitute mint. If provider statuses change at the very end of the interval, this policy may deliberately produce no edition. Explorer does not expose a signed as-of-freeze state: provider coverage and observation timestamps remain trusted inputs.

After sealing, the worker persists the first valid AI direction, creates bounded renderer-v2 geometry, writes/checks artifacts, verifies public CDN bytes and mints exactly that edition into auction custody. AI fallback is disabled; unavailable/invalid direction has a published maximum of three attempts, then requires operator investigation without rerolling frozen inputs. Locked owner curation is read by its Sunday 17:00 UTC deadline; later settlements cannot overwrite historical choices.

## Operations and recovery

Observe Render process health/restarts and PostgreSQL capacity, `/readyz` for API database/schema readiness, `/api/v1/epochs/current` for release and ingestion state, and authenticated `/api/v1/admin/jobs` plus `/api/v1/admin/releases` over the private network. Alert on a failed/stale `live-index`, release `delayed`, `awaiting_signer` when signing should be enabled, unknown chain effects, custody failure, settlement recovery and provider rate limiting. Public API health describes worker-managed integrations and is not proof that credentials work. Route Render logs to the organization's monitoring system; error logs intentionally contain exception types instead of provider bodies/secrets.

Every signing effect stores the exact signed bytes and hash **before** broadcast. Unknown outcomes block new nonce reservation. Startup/tick reconciliation queries final receipts and may rebroadcast the identical transaction; it never signs a replacement merely because of a timeout. Never delete an unknown effect to force progress. If an old transaction cannot be resolved, investigate authoritative RPC history/access-key nonce with an operator; automatic expiry-based replacement is intentionally absent.

Auction status and balances come from finalized onchain views. Lost custody callbacks can be checked again with `retry_custody`; stale callbacks cannot restart the deadline. Lost settlement callbacks are reconciled against the NFT contract's durable auction-delivery record, which remains valid after the winner transfers the NFT onward. Treasury credit is idempotent. Confirmed failed transfers can retry from `RecoveryRequired`; automatic custody/transfer retries have a budget of three. Exhaustion requires investigation. No administrator method redirects escrow to an arbitrary beneficiary.

Receipt indexing is idempotent and accepts only finalized outcomes from the configured contracts. It covers worker operations and wallet receipts submitted through the frontend. It is **not a complete network-wide history index**. Highest bids, refunds and balances remain authoritative onchain. For complete historical analytics commission a reliable NEAR Lake/indexer ingestion source and backfill validated receipts; do not present current partial history as complete.

Enable managed PostgreSQL backups/PITR according to the selected plan and organizational retention requirements; record restore drills. Keep the artifact bucket, protocol commitment and chain-effects journal through recovery. After restoring a backup, start with writes disabled, reconcile every known onchain epoch/commitment and pending transaction before resuming. Do not restore an older database and mint fresh replacements. A failed/irrecoverable frozen release blocks its lineage until resolved; there is no silent skip/reseed mechanism.

## Required release evidence

- Successful container builds and runtime checks on a Docker-enabled Linux host, and managed-cloud rollout/rollback/restore rehearsal.
- Authenticated Explorer capture spanning a real selected checkpoint, provider coverage review and an observed before-freeze reconciliation window.
- Real funded NEAR AI response with persisted model/request/direction, no fallback; replay and public artifact hash verification.
- Deployed reviewed WASM hashes, real mint and custody, at least two signed bids, outbid refund, anti-sniping behavior, successful/failed delivery recovery, winner ownership and exact treasury accounting; inspect complete cross-contract receipts. The legacy compressed testnet runner is a separate integration exercise, not proof of seven-day production timing.
- Independent contract/security review, credential rotation and governance review, plus browser/wallet/mobile accessibility checks.

No item is considered complete merely because a configuration field is populated. No real confidential-swap coverage is claimed until authorized records and source evidence have actually been captured. Nothing in the educational demo proves live financial outcomes.

Provider references: [Render Blueprint specification](https://render.com/docs/blueprint-spec), [background workers](https://render.com/docs/background-workers), [AWS Object Lock bucket configuration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3-bucket.html), [S3 conditional-write enforcement](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html), [NEAR transaction RPC](https://docs.near.org/api/rpc/transactions), [Explorer transaction API](https://docs.near-intents.org/api-reference/get-transactions).
