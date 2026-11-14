# Full testnet rehearsal

This runs the same site and financial contracts as production, with separate
testnet accounts and a test-only clock. No accounts, keys, deploys or mints are
created by preparation. [Initial public testnet deployment is now verified](reports/testnet-deployment-2026-11-14.md):
genesis is in the team wallet and the first synthetic auction has
[settled with delivery and refunds](reports/testnet-auction-settlement-2026-11-14.md).
The winning owner can now test marketplace and early-exit rights. Use the next
fixture in the schedule below for another auction; fresh-workspace instructions
remain available for reproducing the setup.

The saved historical genesis keeps its image, seed, traits and provenance.
Five additional **synthetic** editions exercise auctions and monthly outcomes;
they are not representations of later weeks' real activity. The lab uses known,
historical drand round **6624326**, including real BLS verification. Its result is
predictable and unsuitable for a production draw. Production WASM has neither
the clock methods nor the fixed historical round.

## 1. Configure accounts and tools

Install the [official `near-cli-rs` CLI](https://github.com/near/near-cli-rs#installation)
and authorize testnet accounts using its OS
keychain signer. This workflow never asks for a seed phrase in `.env` or in chat.
Configure these **public account IDs** in the prepared `profile.env`:

| Variable | Purpose |
| --- | --- |
| `TESTNET_GOVERNANCE_ACCOUNT` | Deployer/governance wallet, separate from operator |
| `NEAR_MINTER_ACCOUNT` | Operator: minting, auction creation, lab clock and keeper |
| `NEAR_CREATOR_ACCOUNT` | Team wallet, receives genesis and no-bid editions |
| `NEAR_TREASURY_ACCOUNT` | Receives 20% of primary auction proceeds |
| `NEAR_NFT_CONTRACT` | Fresh NFT/factory account; maximum 40 characters |
| `NEAR_AUCTION_CONTRACT` | Fresh auction account |
| `NEAR_MARKET_CONTRACT` | Fresh marketplace account |
| `TESTNET_ARTIFACT_BASE_URL` | Public HTTPS base URL for the exported `public/` files |

All seven roles must have distinct IDs. Contract accounts must end in `.testnet`;
the account-specific deploy signing keys must also be authorized in the CLI
keychain. The deployer can create these accounts beforehand. This script does not
assume that a parent's key can sign transactions as its subaccount.

Create at least **two additional collector testnet wallets** for bidding,
reselling and offers. Connect them through the site wallet picker, switching
wallet/account between scenarios. Only supported testnet wallets are shown.

Suggested initial **test NEAR** budgets: NFT factory 25, auction 5, marketplace 5,
operator 10, collectors 20 each; team and treasury need existing funded accounts.
These are testing budgets, not exact costs. Keyless edition accounts consume
factory operating reserve for code/storage, separately from auction allocations.

No Explorer JWT, NEAR AI key, 1Click key, mainnet key, backend signer key or admin
token is required for this saved-art rehearsal. The HTTP server never signs.

## 2. Build and prepare

From the repository root (Python 3.12 selected by `.python-version`):

```powershell
uv sync --locked
uv run --locked python scripts/build_contracts.py --test --testnet-lab
uv run --locked python scripts/testnet_rehearsal.py prepare data/replays/2026-11-08-from-1793491200-required-expressive-v4/report.json --name full-lab --full-lab
uv run --locked python scripts/testnet_rehearsal.py fixtures data/testnet-rehearsals/full-lab
```

Rust/Cargo, the WASM target and platform build tools must be installed. Lab WASM
is written to `contracts/target/testnet-lab/wasm32-unknown-unknown/release/`;
embedded vault and hash manifest go to `contracts/artifacts/testnet-lab/`.
Production builds use the original paths. Do not interchange these artifacts.

The current workstation already has an ignored `full-lab` workspace prepared.
Reuse it; preparation refuses to overwrite an existing workspace.

Edit `data/testnet-rehearsals/full-lab/profile.env` using the account table above.
The profile already pins the built WASM hashes and isolated local paths. Upload
**only the contents of `full-lab/public/`**, preserving its directory structure,
to your HTTPS artifact host. Do not upload the workspace, database, logs or CAS
directory. The mint workflow verifies every exported file against its hash.

## 3. Deploy, mint genesis and open the site

```powershell
uv run --locked python scripts/testnet_rehearsal.py check data/testnet-rehearsals/full-lab
uv run --locked python scripts/testnet_rehearsal.py deploy-plan data/testnet-rehearsals/full-lab
```

Review `deploy-plan.json`: account IDs, hashes, testnet network, role bindings,
`new_testnet_lab` initializers and initial clock **15 November 2026 00:00 UTC**.
Use the printed SHA-256 in the next command:

```powershell
uv run --locked python scripts/testnet_rehearsal.py deploy data/testnet-rehearsals/full-lab --send --plan-sha256 DEPLOY_PLAN_SHA256
uv run --locked python scripts/testnet_rehearsal.py check data/testnet-rehearsals/full-lab --online
uv run --locked python scripts/testnet_rehearsal.py mint-plan data/testnet-rehearsals/full-lab
```

Review `mint-plan.json`, then:

```powershell
uv run --locked python scripts/testnet_rehearsal.py mint data/testnet-rehearsals/full-lab --send --plan-sha256 MINT_PLAN_SHA256
uv run --locked python scripts/testnet_rehearsal.py create-wallet data/testnet-rehearsals/full-lab --send
uv run --locked python scripts/testnet_rehearsal.py verify data/testnet-rehearsals/full-lab
uv run --locked python scripts/testnet_rehearsal.py serve data/testnet-rehearsals/full-lab
```

Open **http://127.0.0.1:3004**. API: **http://127.0.0.1:8002**. The original
read-only replay can remain on port 3003. Restart this server after editing its
profile. The wallet must show **testnet**; genesis should appear in the team's
My collection, with frozen artwork traits and a keyless dedicated account.

## 4. Auctions, refunds, trading and ownership

The clock is **frozen**, not a sped-up wall clock. Disconnect wallet actions while
advancing it. All three time-sensitive contracts must agree before the site
enables transactions; health refreshes every 15 seconds.

```powershell
uv run --locked python scripts/testnet_rehearsal.py advance data/testnet-rehearsals/full-lab --to 2026-12-06T00:00:00Z --send
uv run --locked python scripts/testnet_rehearsal.py select data/testnet-rehearsals/full-lab demo-000004
uv run --locked python scripts/testnet_rehearsal.py mint-plan data/testnet-rehearsals/full-lab
# Review the NEW plan/hash for each edition before minting.
uv run --locked python scripts/testnet_rehearsal.py mint data/testnet-rehearsals/full-lab --send --plan-sha256 EDITION_PLAN_SHA256
uv run --locked python scripts/testnet_rehearsal.py tick data/testnet-rehearsals/full-lab --send
```

`tick` creates verified-custody auctions and runs **one explicit keeper pass**.
Dependent receipt stages may need another pass. It never bids, buys, offers,
chooses an exit or transfers a collector's NFT on their behalf.

In `/gallery`, open edition 4's auction. Collector A enters 1 NEAR and clicks
**Place bid**. An unregistered wallet first approves the one-time 0.01 NEAR
registration; after it confirms, the wallet approves the bid. Registered wallets
need only the bid approval. Switch to B and bid at least 1.1 NEAR. Verify A's refund and
reject an under-minimum bid. Advance to `2026-12-07T00:00:00Z`, then `tick` until
the auction is Settled, the winner owns the NFT, the vault is Funded and treasury
credit is paid. With 1.1 NEAR gross, treasury allocation is 0.22 and vault 0.88.

In `/marketplace`, have the owner list in NEAR. Test a fixed-price purchase with
the other collector; verify ownership, seller credit and 5% royalty pool. Test
offers-only listing, escrow offer, offer acceptance, rejected stale rights, offer
cancellation and credit withdrawal. For expiry, advance the lab clock past the
displayed deadline, then release expired records. Rights that change after an
exit require refreshed listing/offer review. Transfers should update My collection.

Repeat the select → mint-plan → reviewed mint → tick sequence:

| Fixture | Advance to before mint | Scenario |
| --- | --- | --- |
| `demo-000005` | 13 December 2026 | Sell at auction; owner uses the 40% early exit in Rewards |
| `demo-000006` | 20 December 2026 | Sell at auction; keep this second eligible draw ticket |
| `demo-000007` | 27 December 2026 | No bids; advance 24h and tick; team receives NFT, no funded ticket |
| `demo-000008` | 3 January 2027 | Sell for January; tests next-month rollover with a new ticket |

Advance 24 hours and settle each auction before moving to the next date. Resales
can happen during December before the month cutoff. Make a resale to a non-team
holder to create a meaningful royalties pool. Ownership changes before cutoff
must change the beneficiary; entitlement already fixed at cutoff must not move.

## 5. Monthly rewards and rollover

Before December closes, use Rewards to withdraw edition 5's 40% allocation as
its current owner. Verify a second exit is rejected, its ticket is excluded and
the remaining 60% of its vault is destined for January. The team-owned unfunded
genesis and no-bid edition create no raffle tickets.

```powershell
uv run --locked python scripts/testnet_rehearsal.py advance data/testnet-rehearsals/full-lab --to 2027-01-01T00:02:00Z --send
uv run --locked python scripts/testnet_rehearsal.py tick data/testnet-rehearsals/full-lab --send
```

Repeat `tick` while state progresses: December closes, vault collections finalize,
the two remaining tickets enter the pot, the historical BLS proof is submitted,
one beneficiary receives the whole pot, and the exited allocation remains in
January's pot. Verify Drawn/Paid, exact balances, fixed winner and rejection of
a second draw. Royalties close sequentially (November first, then December);
repeat ticks until the December ownership snapshot and all share payments finish.
All collection NFTs count equally except those held by team/protocol custody at
cutoff. The raffle and royalties have independent eligibility rules.

Then sell January's fixture, settle it, advance to `2027-02-01T00:02:00Z` and tick
through January. Verify the carried December exit remainder is added to January's
funded pot without granting the exited NFT another ticket. Gas and storage costs
are separate from payout amounts.

## Recovery and acceptance evidence

Every signed operator action is journaled **before** the CLI runs. Unknown results
block further operator writes. Inspect its public explorer receipts; do not delete
the journal to retry. `recover WORKSPACE --tx-hash HASH` verifies the exact signer,
receiver, single call, arguments, deposit and FINAL result for lab clock/keeper
actions. Deployment and mint commands have their own `--failed-tx` recovery flags;
mint `verify` can reconcile successful interrupted mints. A successful recovery
of a failed callback still requires inspecting and retrying the appropriate
published contract recovery method. `operator.lock` left by a process crash must
be inspected and removed only once that process is stopped.

Save transaction hashes and finalized views for each row of the scenarios above.
Native tests and local fixture verification do **not** establish a completed
public testnet test. Browser wallet acceptance, live receipts/gas, RPC reliability
and managed-cloud deployment remain to be exercised with configured accounts.

Cross-chain 1Click funding is deliberately unavailable on testnet: the current
integration settles mainnet assets. Native testnet buys/offers exercise the same
marketplace contract paths. Cross-chain deposit/settlement needs a separate small
mainnet acceptance test after deployment; mock/provider tests are not real swaps.
