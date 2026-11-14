# Intent Distortions

One week of real NEAR Intents activity becomes one permanent artwork.

Intent Distortions turns successful public swaps into collectible generative art. Activity, routes, networks, token diversity and trade sizes shape the geometry and motion. A verifiable seed chooses one of six art families; NEAR AI directs the styling within that family. The accepted direction is saved once. Each edition stores its geometry, renderer and provenance commitments on NEAR, with immutable static and animated SVG views.

The problem: a transaction feed is hard to experience, and a collectible that points to a hosted image depends on that host. This prototype makes network activity visible and keeps the final artwork recoverable from the chain itself.

**This is one testnet application.** Source swaps and block evidence come from mainnet; minting, auctions, sales and rewards use test NEAR. There is no mainnet deployment profile. Cross-chain 1Click checkout is disabled because its mainnet settlement cannot deliver testnet NEAR.

## Try it: do X → see Y

The existing onchain genesis can be viewed without a wallet. Bidding, trading and withdrawals require a funded NEAR testnet wallet. A scheduled auction appears only after a weekly edition has actually been generated, sealed, minted and activated.

| Do | See |
| --- | --- |
| Open **Collection**, then **Echo of the Hub / Genesis** | The first NFT, recovered from `art-v1.id-operator.testnet`, created from 130,086 successful swaps. |
| Switch **Still / In motion** | Two views of the same frozen artwork. The browser verifies their sealed hashes. |
| Open **Drops** | The next release date, live collection/generation progress when running, and previous editions. |
| Connect a testnet wallet; open an active auction; place a bid | Storage registration is included when needed. Wallet approval(s) authorize registration and the bid; the site shows transaction links. |
| Return after its 24-hour deadline | The keeper settles: winner gets the NFT, displaced bids are refunded, and a no-bid NFT goes to the team. Failed transfers remain retryable. |
| Open **Market**, filter listed items or **My items** | NEAR listings, offers, cancellation, purchases and offer acceptance. Approval/storage steps are prepared with the action. Wallet software may still request multiple confirmations. |
| Open **My collection**, then an owned weekly artwork | Current ownership, traits, its dedicated account, and an available early-withdrawal action. Genesis has no auction-funded wallet. |
| Open **Rewards** | Monthly eligible funds/tickets, exits, rollover, draw results and payouts, refreshed from chain state. |

The immutable genesis is `ONCHAIN-PROTOTYPE-000001`. Its [seal transaction](https://testnet.nearblocks.io/txns/AGrn4ChzNKJNsGr25Gx6w2z3B35b87Hg9vZTPqR2PWoa) and [contract](https://testnet.nearblocks.io/address/art-v1.id-operator.testnet) are public. It remains separate from the new auction/rewards collection. Historical financial test contracts and their balances are preserved and are not part of the new schedule.

## Run locally

Install Python 3.12 through uv, Node.js 22, and dependencies. Run from the repository root:

```powershell
uv sync --locked
npm --prefix frontend ci
npm --prefix signer ci
```

For this configured workspace, the private `.env` already preserves the existing provider credentials. On a new checkout, copy `.env.example` to `.env`, fill the three provider fields below and the deployed code pins. Do not run `configure` against a hosted profile: it intentionally resets local paths and disables automation/signing.

```powershell
uv run --locked python scripts/prototype.py serve
```

Open **http://127.0.0.1:3000** → see genesis, the weekly schedule and live testnet views. This local launcher disables the scheduler and server signing; wallet-authorized actions still work against deployed contracts. Ctrl+C stops both servers. Fresh weekly contracts must be deployed before their financial views/actions are available.

Required server integration settings:

| Setting | Purpose |
| --- | --- |
| `NEAR_INTENTS_PARTNER_JWT` | Explorer key for successful mainnet swap records. |
| `NEAR_AI_API_KEY`, `NEAR_AI_TEXT_MODEL` | NEAR AI Cloud artistic direction. No fallback is allowed for weekly editions. |
| `NEAR_RPC_URL` | Healthy NEAR testnet RPC for contracts and wallets. |
| `NEAR_MAINNET_RPC_URL` | Archival mainnet block verification for source checkpoints. |
| `NEAR_*_ACCOUNT`, `NEAR_*_CONTRACT`, `EXPECTED_*_CODE_HASH` | Public role bindings and reviewed binaries. |

No Cloudflare, S3, IPFS, public artwork URL, 1Click key, mainnet signing key or wallet seed phrase is needed. The private source archive still needs durable disk storage for reconciliation and restart recovery; it is not the NFT's media host.

## Weekly mechanics

The first new releases are **November 15, 22 and 29, 2026**, all using normal auctions. Weekly releases continue after that. At Sunday 18:00 UTC, a fixed drand round selects a mainnet checkpoint from that Sunday's 00:00–17:00 window. Successful records are filtered to the exact half-open nanosecond interval, deduplicated and reconciled across two complete observations before the fixed freeze (normally 19:00 UTC). The first interval starts at the preserved genesis endpoint, November 8 at 02:57:10.218994184 UTC; subsequent intervals continue from the previous endpoint without gaps or overlaps.

After validation, the worker persists the AI direction, geometry and commitments; uploads the IDART1 recipe in chunks; verifies the static and animated hashes in separate transactions; and seals/mints the NFT into auction custody. It funds a keyless dedicated edition account and opens the 24-hour auction. A missing/mismatched source observation stops the release instead of substituting data or rerolling it. A missed freeze without saved valid observations requires operator investigation.

Each NFT is NEP-171. Standard `nft_token` exposes an embedded SVG; low-gas ownership/enumeration calls use compact metadata. The onchain recipe and pinned renderer reconstruct both views without IPFS or a separate artwork host. Transfer changes the owner, not the recipe, AI direction or SVG hashes. The fresh contracts are deployed atomically with **no access keys** and expose no upgrade/replacement method.

## Collection economy

Successful auctions allocate **20% to treasury, 80% to the edition account**. A current holder may withdraw **40% of that 80% allocation**, once, before its month closes. The remaining 60% rolls to the next monthly pot; that edition forfeits its draw entry permanently. Eligible editions contribute their full allocation and one ticket. At UTC month end, the contract snapshots beneficiaries, collects wallets and verifies a predetermined drand proof to choose a winner. The keeper submits calls and proofs; an AI agent does not choose the winner. Empty pots/ticket sets carry forward under contract rules.

Dedicated addresses follow `november2026-edition-1.<nft-contract>`. They are contract-controlled, keyless subaccounts. Holders authorize constrained actions through the NFT contract; they do not receive a private key or arbitrary spending access. Current ownership and in-flight transfer locks prevent a seller from using the new owner's unused rights. A withdrawal already authorized before a sale remains payable to its recorded beneficiary. The remaining rights/balance travel with the NFT. Full transfer, payout and stale-snapshot cases are covered in the contract tests.

Marketplace sales charge **5%**, distributed equally per eligible artwork across the weekly collection at UTC month end, excluding the team wallet. Owning multiple eligible editions earns multiple shares. The separately preserved genesis is not counted by the fresh financial contracts.

## Deploy and verify

See [the deployment guide](docs/managed-cloud.md) for fresh testnet contracts, Vercel + Render hosting, signer configuration and the automation switch. [project.json](project.json) describes the same product, networks, accounts, commands and routes for a machine reader. [The onchain format](docs/ONCHAIN_ART.md) explains what is stored and frozen.

```powershell
uv run --locked pytest backend/tests -q
uv run --locked python scripts/run_demo_epoch.py
uv run --locked python scripts/verify_epoch.py
uv run --locked python scripts/validate_deployment.py
node --test signer/signer.test.mjs
node --experimental-strip-types --test frontend/tests/*.test.mjs
npm --prefix frontend run build
```

Synthetic fixtures and isolated lab utilities remain development/test tools; they are not separate shipped applications. Earlier testnet receipts in `docs/reports/` document previous rehearsals, not deployment of the fresh weekly accounts. See [current validation status](docs/VALIDATION.md) before judging a check as completed.
