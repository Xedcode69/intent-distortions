# Marketplace and holder royalties validation — 2026-11-13

Implemented secondary listings, offer-only listings, native NEAR purchases, escrowed expiring offers and cancellations, seller/refund credit withdrawals, 1Click cross-chain funding, and monthly full-collection holder royalties. The fee is deducted from gross sale proceeds: 95% seller credit, 5% holder pool. Primary auction accounting remains separate.

Validation:

- **Python: 124 passed, 1 skipped.** The optional PostgreSQL integration test had no dedicated URL configured. Existing Starlette deprecation warning remains. Tests cover provider quote destination/amount/refund invariants, response privacy, contract bindings/hash/fee policy, disabled replay checkout, deterministic royalty maintenance, receipt finality/executor filtering and the existing artwork/economy pipeline.
- **Rust: 62 passed** (18 auction, 13 marketplace including shared calendar, 27 NFT, 4 vault). New cases cover duplicate/failed sales, relisting nonces, simultaneous buys, underpayment, offer escrow/cancellation, authorized acceptance, withdrawal retries, 5% fee allocation, per-NFT shares, creator/custody exclusion, dust/no-holder rollover, duplicate payout rejection, failed royalty retry, permanent ownership checkpoints and stale financial-state rejection.
- **JavaScript: 13 passed.** Integer royalty/amount formatting and existing signing, proxy, family-selection, provenance and accounting checks passed. The worker signer accepts only marketplace snapshot preparation and fixed-beneficiary royalty delivery; it rejects purchases and credit withdrawals.
- **Next.js production build / TypeScript passed.** `/marketplace` is included. HTTP checks returned 200 for the read-only marketplace and historical demo; no fake collection listings, offers or fee balances are returned, and replay cross-chain requests are rejected. All historical PNG/scene/trait hashes still match. Browser wallet/mobile visual QA was not performed.
- Root epoch replay verification passed. Render Blueprint validation against its vendored official schema and deployment isolation checks passed.
- A credential-free request to the live official 1Click API found **231 supported catalog assets** and successfully validated an `EXACT_OUTPUT` dry quote for **1 NEAR**. No deposit address was created and no funds were sent. Mock tests also preserve required deposit memos. Real funded cross-chain settlement remains acceptance work.

## Real WASM sandbox

The final production WASM ran in a disposable official NEAR **2.14** sandbox. The lifecycle passed:

1. Seven dedicated keyless edition accounts, scheduled creator mints, 24-hour auctions, automatic losing-bid refunds and no-bid creator delivery.
2. A noncustodial 10 NEAR resale credited the seller 9.5 NEAR; an accepted 4 NEAR offer credited its seller 3.8 NEAR. Seller credit withdrawal succeeded.
3. A revoked approval rejected a 9 NEAR purchase, preserved NFT ownership, charged no royalty and returned the full payment as withdrawable buyer credit.
4. Secondary sales totaled **14 NEAR**, with **13.3 NEAR** for sellers and **0.7 NEAR** in royalties. At cutoff, four collector-held NFTs each received **0.175 NEAR**; the three team-held NFTs received no shares. A holder with two NFTs earned two shares. One NFT transferred back to the team after cutoff still paid its previous collector's fixed entitlement.
5. All four royalty payments completed and the royalty pot reached zero. These funds did not enter the primary raffle or refill a vault.
6. Secondary ownership still inherited the unused early-exit right; the one-time withdrawal, next-month rollover, collected pot, verified drand draw and failed-prize delivery/retry all passed with the new ownership-history writes.

As in previous reports, the sandbox uses a long local validator epoch for fast calendar advancement and changes only the local month's expected beacon round to a captured historical fixture to exercise the real BLS host verification. The production contracts contain no test setter. No real-network deployment, NFT mint, bid or transfer occurred.

## Current candidate hashes

| WASM | SHA-256 |
| --- | --- |
| Marketplace | `1992413e17fcc6e5c28b56f84adba71fb1fdd64d5169e32fb3e44acbee9c48fc` |
| NFT | `4f495c1b235bccfd9caf529ba212528d16c8d21e7470b692f7768d370b884a0a` |
| Auction | `3198e091c247facb14e4767def8313f4c1e64e7ae0f40f2f39e88b8d8ef76e9f` |
| Vault | `0bd2832599944647bcf6d019600409d1e709efe9eb4a1e24d0641c943af9b2f1` |

The NFT hash supersedes prior candidate hashes. Its ownership-history fields change state layout: use a fresh deployment or separately review a migration. Pin both current NFT and marketplace code hashes. Independent contract review, funded testnet acceptance, real mainnet cross-chain acceptance and browser/wallet QA remain release gates. Marketplace-only fee enforcement, funding-before-purchase semantics, storage sponsorship and retry behavior are detailed in [MARKETPLACE.md](../MARKETPLACE.md).
