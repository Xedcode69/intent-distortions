# Edition economy validation — November 13, 2026

Implemented policy: November 15/22/29 creator editions; December 6 onward 24-hour auctions; dedicated keyless edition accounts; 20% treasury / 80% edition allocation; one early withdrawal of 40% of the original allocation; exclusion and next-month rollover; one ticket per remaining eligible NFT; fixed-round drand verification and whole-pot prize delivery. See [ECONOMY.md](../ECONOMY.md) for exact boundaries and deployment instructions.

## Contract validation

46 native Rust tests pass: 18 auction, 24 NFT/calendar/randomness/economy, 4 dedicated-vault tests. Three release WASM artifacts build with Rust 1.95.0 and NEAR SDK 5.30.1. The same final artifacts passed the real cross-contract NEAR Workspaces lifecycle on official sandbox **2.14.0**, protocol 88. This is a local chain, not a testnet or mainnet deployment.

The sandbox test creates seven dedicated accounts and confirms each has no access keys. It checks the three creator mints, monthly account numbering, auction custody, automatic refunds, fixed deadlines, successful allocation, no-bid return to creator, secondary transfer, rejected transfer-call recovery, one-time exit, collection and rollover. It also verifies a captured drand signature through the actual BLS host functions, rejects invalid/repeated draws, deliberately causes a prize transfer failure, confirms the fixed winner/amount remain retryable, then verifies successful retry and treasury delivery.

The three successful sandbox auctions sell for 110 NEAR each:

| Destination | Sandbox NEAR |
|---|---:|
| Treasury | 66 |
| One early withdrawal | 35.2 |
| Prize, two eligible NFT tickets | 176 |
| Next-month rollover | 52.8 |
| **Total** | **330** |

Separately, native accounting tests cover five 100-NEAR sales and two exits: 100 treasury, 64 withdrawals, 240 current prize contribution, 96 rollover, three tickets.

The sandbox uses a long local validator epoch to make calendar fast-forward practical. Its clock can overshoot requested dates, so tests derive the funded month from actual contract state. To test the verifier and payout before the future monthly beacon exists, sandbox-only state intervention substitutes captured drand round **6624326**. Production WASM contains no round setter; it fixes the future round from the UTC month cutoff. This test does not claim a real future draw has happened.

## Final artifact SHA-256

| Artifact | SHA-256 |
|---|---|
| echo_vault.wasm | `0bd2832599944647bcf6d019600409d1e709efe9eb4a1e24d0641c943af9b2f1` |
| echo_nft.wasm | `f6198e678f7d41c6cc04f3f563d3578ccbcf183cdcaa307fee35a3ae519bd870` |
| echo_auction.wasm | `3198e091c247facb14e4767def8313f4c1e64e7ae0f40f2f39e88b8d8ef76e9f` |

The factory embeds the exact listed vault bytes. A different platform/toolchain can produce different bytes; pin the actual reviewed artifacts used for deployment.

## Application and publication checks

The production Next.js build and TypeScript validation pass. Eleven Node tests pass across accounting examples, signer scope, API proxy restrictions, independent artwork verification and family selection. All **107 Python tests pass**, including the disposable PostgreSQL migration/advisory-lease test. Coverage includes economic preflight, fixed-round keeper behaviour, incomplete-collection gating, known-failure isolation, unknown-nonce blocking and read-only API behaviour.

The local read-only preview serves `/demo`, `/economy` and `/treasury` over HTTP. It reports `not_deployed`, zero earned funds and no invented accounts or pots. The historical artwork remains a saved real-data result; its new financial simulator is separately labelled. The existing artwork provenance/re-render check passes. Credential scanning covers intended public source and historical assets without publishing credential values. Browser playback/visual QA was not performed in this task.

## External acceptance gates

No real-network mint, auction, withdrawal or raffle was executed. Fresh accounts, creator/treasury bindings, reviewed artifact hashes, operating reserves, managed storage/database services and a constrained signer must be configured. Real testnet acceptance, independent contract/security review, account upgrade/key policy and jurisdiction-specific legal clearance remain required before accepting real money. The release archives continue to declare themselves candidates and `mainnet_ready: false`.
