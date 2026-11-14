# Deploy the testnet prototype

The frontend runs on Vercel. One continuously running Render web service hosts the API and a single leased weekly worker, sharing PostgreSQL and a persistent source-archive disk. A serverless function cannot run the weekly collector/keeper continuously. No separate demo, S3 bucket or public artwork host is deployed.

## 1. Build and deploy fresh testnet contracts

Install Rust 1.95.0 with `wasm32-unknown-unknown`, a native C/C++ linker, and the official NEAR CLI. Authorize `id-operator.testnet` in the CLI OS keychain. The operator creates three direct children without access keys; neither the old contracts nor their reward funds are upgraded or swept.

```powershell
uv run --locked python scripts/build_contracts.py --test
uv run --locked python scripts/prototype.py configure
uv run --locked python scripts/prototype.py plan
```

`configure` migrates the needed existing local provider credentials, sets the new public account IDs and pins from `contracts/artifacts/testnet/build.json`, and disables automation. It removes old artwork-host/S3 settings from the active `.env`. Review the printed plan, deposits and SHA-256. Optional Binaryen 125 optimization: pass `--optimizer-js <verified-wasm-opt.js-path>` to the build. Pin the resulting build, not a hash from a different machine/profile. Never use `--testnet-lab` for the public weekly deployment.

```powershell
uv run --locked python scripts/prototype.py deploy --send --plan-sha256 <printed-plan-sha256>
```

The script inspects the exact signed CreateAccount/Transfer/Deploy/Init actions before broadcasting, journals signed bytes first, waits for FINAL and verifies bindings, code hashes and absent access keys. Existing matching code is inspected, never upgraded. A lost response stops new signing. Read the exact saved outcome with `prototype.py recover --role nft` (or `auction` / `market`) before resuming. Do not delete the journal or re-sign an ambiguous transaction.

The operator must cover actual code/storage deposits and gas. The plan reports calculated setup cost; artwork upload and edition-account storage are additional per edition. No arbitrary aggregate NEAR balance threshold is imposed. Account-level funds reserved for rewards remain protected by contract liability checks.

```powershell
uv run --locked python scripts/prototype_preflight.py --online
```

See `data/prototype/deployment-verified.json` and private receipt journals → verify fresh accounts are keyless and bindings match. Genesis remains in `art-v1.id-operator.testnet`; do not redeploy it.

## 2. Host the backend

Create a Render Blueprint from `render.yaml`. Supply the requested private provider credentials and public code pins. Set `PUBLIC_ORIGIN` and `CORS_ORIGIN` to the Vercel HTTPS origin. Set `ALLOWED_HOSTS` to a JSON array containing the Render service hostname (no scheme), plus `localhost` if needed. PostgreSQL is wired by the Blueprint; migrations run before deployment. Keep one service instance and the disk mounted at `/app/data`. Back up both PostgreSQL and this disk; their persisted snapshots, accepted direction and signed journals are needed for safe recovery.

The container builds its native frozen-SVG serializer from the same Rust renderer source embedded in the contract. `APP_ENV=production` means a hardened hosted **testnet** server; it never selects mainnet. The server rejects `NEAR_NETWORK=mainnet`.

Initially leave `ENABLE_CHAIN_WRITES=false`. The scheduler can validate and persist source observations but cannot mint or settle until signing is enabled. Mount a Render secret file named `near-worker.json` at `/etc/secrets/near-worker.json`, containing the operator's `account_id`, `public_key` and `private_key` JSON fields. Use a dedicated operator key. Keep it out of Git, the frontend and `.env`. The signer checks account/network, approved receiver/method, gas and attached-deposit caps. CLI OS-keychain access is only for local bootstrap; the hosted signer cannot read your desktop keychain.

Run the read-only online preflight with the hosted settings, then set `ENABLE_CHAIN_WRITES=true` and redeploy before the first Sunday observation/freeze window. `SERVICE_ROLE=combined` and `SCHEDULER_ENABLED=true` start the leased weekly worker. The same worker reconciles unknown signed outcomes, activates auctions, settles deadlines, retries refunds/funding and processes monthly draws/royalties. It runs during long Explorer captures as well. `/api/v1/health` reports automation state; `/readyz` returns 503 if the combined worker has stopped. Alert on failed readiness and `Release.error` / unknown `Effect` entries.

## 3. Host the frontend

Import the GitHub repository into Vercel, choose **Next.js**, and set **Root Directory = frontend**. `frontend/vercel.json` supplies `npm ci` and `npm run build`. Set server-only `BACKEND_URL=https://<render-service>.onrender.com` and `APP_PROFILE=testnet`. Redeploy → see the genesis and upcoming Drops. No AI, Explorer, signer or wallet private credentials belong in Vercel or `NEXT_PUBLIC_*` variables. Connect funded testnet wallets through the UI.

## 4. Check the full release

Do the README walkthrough. Before the first release, Drops shows the upcoming November 15 schedule and preserved genesis. During the observation window, progress should change. After a valid freeze → onchain static + animated edition → dedicated account → active 24-hour auction. Use two bidder accounts; confirm refunds, final winner ownership, 20/80 allocation and the wallet balance. A no-bid edition goes to the team. Do not shorten the real public schedule to simulate month end; use isolated development tests for clocks and historical draw proofs.

Hosting references: [Vercel build/root settings](https://vercel.com/docs/builds/configure-a-build), [Vercel environment variables](https://vercel.com/docs/environment-variables), [Render persistent disks](https://render.com/docs/disks). A Render disk belongs to one service, which is why API and worker share one process rather than two services with disconnected local archives.
