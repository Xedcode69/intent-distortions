# NFT and auction contracts

Pinned SDK and standards: **5.30.1**. Required compiler: **Rust 1.95**. Run native tests and build WASM:

```text
cargo +1.95.0 test --locked --manifest-path contracts/Cargo.toml --workspace
cargo +1.95.0 build --locked --release --target wasm32-unknown-unknown --manifest-path contracts/Cargo.toml
```

Artifacts: `contracts/target/wasm32-unknown-unknown/release/echo_nft.wasm` and `echo_auction.wasm`. For reproducible production deployment use a pinned Linux build container/cargo-near toolchain, archive its source commit and artifact hash, and perform an independent contract review. Unit tests are not a substitute for testnet/sandbox cross-contract execution.

## Initialization

Create dedicated funded testnet contract accounts and an operator/minter account using the [official CLI](https://github.com/near/near-cli-rs/blob/main/docs/GUIDE.en.md). Keep account signing in the OS keychain.

Production NFT **`new_production`** arguments (the legacy `new` initializer remains for isolated lab contracts):

```json
{"owner_id":"governance.testnet","minter":"operator.testnet","auction_contract":"echo-auction.testnet"}
```

Auction `new` arguments:

```json
{
  "owner":"operator.testnet",
  "nft_contract":"echo-nft-demo.testnet",
  "treasury_accounts":["creative.testnet","development.testnet","community.testnet"],
  "splits":[6000,2500,1500],
  "min_bid":"1000000000000000000000000",
  "increment":"100000000000000000000000",
  "demo_duration_seconds":null
}
```

For the seven-day policy pass `demo_duration_seconds:null`. A compressed duration is accepted only for contract account IDs ending in `.testnet`, with bounds 30–3600 seconds; rolling extension is ten seconds in this compressed configuration. Production uses a five-minute rolling extension. All timing is contract-enforced. Keep the operator account the same as the configured minter for the supplied lifecycle runner.

Deploy with the official `near contract deploy <contract> use-file <wasm> with-init-call <initializer> json-args '<json>' prepaid-gas '100 Tgas' attached-deposit '0 NEAR' network-config testnet sign-with-keychain send`. Use `new_production` for NFT and `new` for auction. This is a real signed action. No deployment has been performed in this workspace. Fund contract accounts sufficiently for state storage and one-yocto NFT transfer calls. Worker and auction accounts cannot also be treasury withdrawal accounts. Never deploy changed state layouts over an initialized legacy contract without a separately reviewed migration; use fresh accounts for this release candidate.

## NFT invariants

`mint_weekly_artwork(receiver_id,metadata,commitment)` is restricted to the minter. Commitment includes epoch, image/provenance hash, Merkle root, seed and block hash. The contract enforces one token per epoch, one image hash, `copies=1`, and metadata hash equality. Mint storage includes custom commitment records; only measured surplus is returned. Standard NEP-171 transfer, approval, enumeration and metadata interfaces delegate to the official standards implementation. NFT events use the standard event emitter.

The minter must verify all offchain evidence before signing. The contract cannot establish that the Explorer dataset is complete or verify the offchain drand beacon; it enforces immutable commitments and mint uniqueness.

## Auction invariants

1. Mint the NFT directly to the auction contract.
2. Operator calls `create_auction` with 0.05 NEAR for bounded listing storage.
3. A private callback checks the configured NFT contract's returned owner and token ID. Bids remain disabled until custody succeeds.
4. Each bidder calls `register_bidder` once with at least 0.01 NEAR for its fixed refund balance storage; this storage reserve is distinct from a bid. Registration surplus is credited to the bidder's refundable balance.
5. `place_bid(token_id)` uses attached native NEAR as the complete bid. Require minimum reserve/increment and an open deadline. Previous highest bid becomes independently claimable; rebidding by the same account follows the same accounting rule.
6. After effective deadline anyone calls `finalize_auction`. Status becomes pending before issuing `nft_transfer`.
7. Successful transfer marks settled and allocates 60/25/15 (or initialized basis points). Failed transfer retains all escrow and marks recovery-required; a later call can retry. No-bid editions return to the creative treasury, become unsold, and never remint.
8. Refunds and treasury proceeds are pulled by their entitled accounts with exactly one yocto attached. Debit before transfer; a private failure callback restores the amount. Concurrent fresh credits remain intact.

The first two treasury allocations use integer floor arithmetic; all remaining units go to community. Treasury withdrawals are restricted by the entitlement map, not the art worker. The contract emits NEP-297 formatted custom events for custody, bids, settlement, and cash claims. The receipt index verifies observed worker/first-party wallet receipts; it is explicitly partial and is not a network-wide event index.

`choose_theme(theme)` permits celestial/organic/crystalline only. It queries ownership of the most recently settled NFT, checks the next Sunday 17:00 UTC lock deadline both before and after the async ownership query, then stores the permitted style choice. `get_theme` reveals current rights; `get_theme_for(deadline_ns)` preserves the choice for a specific Sunday so a later settlement cannot overwrite the locked historical value. Non-demo generation reads that deadline-specific locked choice. Organic selects branching fibers, crystalline selects faceted geometry, and celestial preserves the selected direction. The seed remains unchanged. The choice and applied policy are recorded in provenance. This cross-contract creative flow still needs credentialed end-to-end testing.

## Recovery limits

An uncertain offchain response never justifies a second mint: query `get_epoch_token`, `get_provenance` and `nft_token`. The worker journals exact signed bytes before broadcast and blocks new nonces while an outcome is unknown. `retry_custody` recovers missing/failed initial custody callbacks without restarting an active auction. `reconcile_settlement` checks the configured NFT's durable `get_auction_delivery` record; treasury allocation remains idempotent even if the original callback was lost and the winner subsequently transfers the NFT. If no delivery exists and NFT custody remains with the auction, recovery can return to `RecoveryRequired` for a bounded retry. There is no administrator function that redirects escrow. Native tests cover these state transitions; real cross-contract gas/callback execution and independent review remain release gates. See [managed-cloud operations](managed-cloud.md).
