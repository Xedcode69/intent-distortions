# Dedicated edition accounts and monthly economy

This release implements the financial layer in `echo-nft` (NFT ownership and monthly coordinator), `echo-auction` (24-hour escrow) and `echo-vault` (one keyless NEAR account per edition). These are new state layouts: deploy to fresh accounts. Never deploy these bytes over an initialized older contract without a separately reviewed migration.

## Fixed launch and naming

The schedule is enforced against each edition's Sunday UTC date, not the operator's chosen mint recipient. Epoch 1 is November 15, 2026. November 15/22/29 and all subsequent editions mint into auction custody for normal 24-hour auctions. The separately preserved onchain genesis has no auction-funded financial rights. Dates cannot be duplicated, pre-minted or mismatched with epoch numbers. Delayed publication retains its scheduled edition name.

Account names are `monthYEAR-edition-N.<complete-nft-account-id>`, all lowercase. November's launch editions are `november2026-edition-1`, `-2`, `-3`; December restarts at `december2026-edition-1`. Subsequent months number their scheduled Sundays starting at one. The complete account must fit NEAR's 64-byte limit, so the NFT contract account is limited to 40 bytes. Example: `december2026-edition-1.weekly-nft.id-operator.testnet`. A testnet deployment appends its complete `.testnet` account instead. A bare top-level name such as `december2026-edition-1.near` is not created by this factory: it would need separate registration.

Each mint's NEP-177 metadata `extra` links the dedicated account, controller, scheduled date and policy. Creating the account is a separate recoverable operation after minting. The factory creates the child account, transfers an operating/storage reserve, deploys the embedded vault WASM and initializes it in one batch, without adding access keys. There is no vault method for arbitrary calls, adding keys, upgrading code or redirecting funds. NFT owners authorize economic rights through the NFT contract; they never receive a vault private key. Unsolicited deposits to vault accounts are not counted as auction allocations and have no withdrawal entitlement.

## Accounting rules

Native NEAR is the only settlement currency. For a successful sale `P`, treasury receives `floor(P/5)` and the vault receives the remainder. A one-time early exit pays `floor(original_vault_allocation * 2/5)` and reserves the rest for next month's pot. Storage deposits, account startup costs and gas are separate from `P`. The coordinator tracks outstanding hub liabilities and cannot spend them creating more accounts.

For five 100-NEAR sales and two exits: treasury 100; early withdrawals 64; current pot 240 with three tickets; next-month rollover 96. Total 500. Amounts are integer yoctoNEAR throughout; rounding remainders stay in the vault/pot, never disappear.

The 24 hours starts only after NFT custody is confirmed. There is no rolling extension. An outbid bidder's balance is debited and an automatic refund attempted. Failed refunds restore an independently claimable credit; `process_refund(account)` lets any keeper retry payment to that fixed account. One failed recipient cannot block settlement. A no-bid edition goes to the creator, without a funded raffle ticket.

Settlement first transfers the NFT and confirms its durable delivery record. Then the auction forwards the entire winning bid to the NFT coordinator. Only that configured auction can fund an edition, once. Treasury and vault allocation are recorded there, and the keeper funds the dedicated vault. The auction remains `FundingPending` until allocation is confirmed. Known failed funding is retryable; unknown results are checked against the durable receipt and are not blindly resent.

## Ownership, exits and monthly cutoff

The current owner may call `withdraw_edition` with one yoctoNEAR before the funded calendar month's cutoff. The contract records the exit and fixes its beneficiary before calling the vault. Transfers cannot reset that choice. Failed withdrawal delivery remains reserved for the original requester and is retried with `dispatch_exit` or the vault's fixed payment retry. The balance is not made available for spending again.

Direct NFT transfers update the economic beneficiary only before the UTC cutoff. `nft_transfer_call` marks rights pending until the standard resolver completes; temporary receivers cannot withdraw or forward a pending NFT. A rejected transfer restores the original owner. A transfer finalized after cutoff does not change the already fixed monthly entitlement. Closing a month waits for transfer resolution and all wallet funding, even when the keeper runs late.

The cycle is assigned when the auction proceeds arrive at the coordinator, not from the artwork's date. This handles delayed auctions and auctions crossing month-end explicitly. Each allocation participates in one funded cycle. One eligible NFT is one ticket; multiple eligible NFTs give their owner multiple tickets. Early-exited NFTs never gain another ticket from their rollover. Creator/unsold editions have none unless a future, separately specified funding mechanism is implemented.

At close, eligible allocations target the current pot; exited remainders target the next pot. The source and destination receipt counters prevent a draw before all contributions arrive. Months close sequentially, and a later cycle cannot close while its predecessor is unfinished. Anyone may collect an edition after closure. Each vault's early payment and collection are separately reserved and idempotent. Collection rejects an incorrect amount or a missing early-withdrawal reservation.

After the monthly draw, all participating allocations have been consumed. Non-winning NFT owners keep the art, not their former pooled balance. This is redistribution of primary auction proceeds; no external yield or guaranteed return is created.

## Randomness and payout

The coordinator pins the drand default chained network public key and parameters. Every month's round is the first round at or after one minute past its UTC cutoff, fixed by code. The artwork seed is never used. Anyone may relay that round's signature and previous signature. The contract implements RFC9380 XMD/hash-to-field and uses NEAR's NEP-488 BLS12-381 host functions for mapping, group addition, decompression and subgroup-checked pairing verification. Neither a caller-supplied public key nor an AI-proposed winner is accepted.

The eligible token IDs are sorted. A domain-separated hash of the verified entropy and cycle selects an index using rejection sampling. There is no reroll, selectable alternate round or administrative winner setter. A missing beacon delays that same draw. Zero tickets carries the whole pot forward; one ticket needs no random choice. The selected beneficiary and entire prize are fixed before transfer. A failed payout remains retryable for that beneficiary without selecting another winner.

The RPC/runtime must support the pinned SDK's host functions. Validate the exact WASM on a compatible NEAR sandbox and testnet before accepting funds. The SDK 5.30.1 native tests use nearcore 2.14 runtime bindings. A successful native test is not proof that an arbitrary older node can execute these imports.

## Keeper and managed deployment

`backend/app/services/economy_keeper.py` is deterministic automation, invoked by the existing leased production worker. It processes auction recovery, proceeds, refunds, wallet creation/funding, requested exits, monthly collection, fixed-round proof submission, prize retries and treasury payments. All maintenance methods use zero deposit and fixed contract destinations. The isolated signer allowlists methods and rejects value-bearing maintenance calls. Existing exact-signed-byte journaling and unknown-outcome nonce blocking are preserved. AI Cloud remains responsible for creative styling, not money decisions. The experimental Agent API is not required or given custody.

Deploy fresh funded NFT/auction accounts with `new_economy`:

```json
{"owner_id":"governance.testnet","minter":"operator.testnet","auction_contract":"auction.echoes.testnet","creator":"team.testnet","treasury":"treasury.testnet"}
```

```json
{"owner":"operator.testnet","nft_contract":"nft.echoes.testnet","creator":"team.testnet","treasury":"treasury.testnet","min_bid":"1000000000000000000000000","increment":"100000000000000000000000"}
```

The first object initializes NFT; the second initializes auction. Creator/treasury bindings must match across contracts. Build the vault first and embed exactly those bytes in NFT:

```text
uv sync --locked
uv run --locked python scripts/build_contracts.py --test
uv run --locked pytest backend/tests -q
```

The build writes three WASM artifacts and `contracts/artifacts/hashes.json`. Pin all three reviewed hashes in the environment. `FIRST_RELEASE_SUNDAY=2026-11-15`, `ECONOMY_ENABLED=true`, `NEAR_CREATOR_ACCOUNT`, `NEAR_TREASURY_ACCOUNT`, and `EXPECTED_VAULT_CODE_HASH` are additional deployment settings. Existing Explorer, AI, archival RPC, PostgreSQL, persistent source-archive disk and isolated signer settings still apply. The wallet startup reserve is calculated from the actual embedded code length plus state headroom; fund the coordinator's operating balance separately. Function-call keys cannot attach native NEAR: a dedicated limited keeper can call maintenance, while mint/list publication needs its separately constrained deposit-capable signer.

The `/economy` page (also `/treasury`) shows live monthly aggregates: eligible draw funds, eligible artwork count, early withdrawals, incoming rollover and next-month rollover. It includes funded allocations held in edition wallets without counting collected funds twice. Closed draws show their frozen tickets, final prize, winner and payment state. Totals refresh every 30 seconds; manual Refresh reads a new pinned snapshot. Individual NFT balances, withdrawals and transfers belong in the owned-artwork detail view in My collection. The historical `/demo` keeps its clearly marked financial simulator with no accounts or funds; it does not claim the saved artwork was auctioned.

## Acceptance and remaining external gates

Native tests cover schedule/naming, account actions without keys, the five-sale/two-exit accounting, owner changes, cutoff boundaries, replay rejection, pending/rejected NFT transfers, failed funding, failed payments, no-entry carry and real drand verification. `contracts/integration/lifecycle.test.mjs` executes the exact WASM in NEAR Workspaces, checks account keys and cross-contract receipts, and exercises automatic refunds, secondary ownership, exit, rollover and prize delivery. Because the future monthly beacon does not exist at development time, the sandbox explicitly patches only its test state's expected round to a captured historical beacon; no test setter is compiled into the contracts. Production always computes the future round.

The integration suite needs Linux with GLIBC 2.39 or newer (Ubuntu 24.04+, or a `node:22-trixie-slim` container). The official 2.14 binary cannot run on Debian Bookworm's older GLIBC:

```text
cd contracts/integration
npm ci --ignore-scripts
npm test
```

Use a pinned compatible `SANDBOX_ARTIFACT_URL` or sandbox binary, not an unreviewed default node release. CI runs the sandbox after building the current artifacts. Local sandbox tests are not a real testnet deployment or an independent audit. Before real-money launch, record credentialed testnet acceptance, commission independent contract/security review, establish account upgrade/key policy and monitoring, and obtain jurisdiction-specific legal clearance for the paid chance-based cash prize. No mainnet deployment or signing is performed by this implementation task.

On Windows with Docker Desktop running, use `powershell -File scripts/test_economy_sandbox.ps1`. It mounts only contracts/public fixtures into an isolated Linux container. A corporate CA can be supplied with `-CaFile <certificate-bundle-path>`; certificate verification stays enabled.
