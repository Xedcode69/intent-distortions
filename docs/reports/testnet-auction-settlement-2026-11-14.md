# Public testnet auction settlement — 14 November 2026

One public testnet auction has completed with wallet-authorized bids, automatic
outbid refunds, confirmed NFT delivery and the 20/80 allocation. This validates
that scenario on the lab builds; it is not mainnet acceptance or a completed
marketplace/monthly-rewards test.

The lab clock advanced from 6 December 2026 00:00 UTC to the auction deadline,
7 December 2026 00:00 UTC. These are controlled contract dates, not the real
calendar date of this test.

## Final outcome

| Check | Verified result |
| --- | --- |
| Auction / edition | `ECHO-000004`, synthetic fixture, status `Settled` |
| Highest bid | 1.5 test NEAR |
| Winner and finalized NFT owner | `iddeployertest.testnet` |
| Dedicated account | `december2026-edition-1.id-nft.testnet` |
| Vault state | `Funded`; original and available allocation both 1.2 test NEAR |
| Monthly beneficiary / cycle | Winning owner; December 2026 (`202612`), no exit used |
| Treasury | 0.3 test NEAR delivered to `id-treasury.testnet` |
| Pending treasury payment / credit | None / zero |
| Coordinator financial liability | Zero after forwarding the allocations |
| Unpaid bidder refund credits | Zero for both participating wallets |

The treasury account's before/after balance increased by exactly 0.3 test NEAR.
The vault's economic allocation is checked separately from its operating/storage
reserve. Contract code hashes and policies were reverified before settlement.

## Bid principal and refund receipts

| Bidder | Bid | Outcome |
| --- | ---: | --- |
| `iddeployertest.testnet` | 1 test NEAR | Fully refunded when outbid |
| `idtester1.testnet` | 1.3 test NEAR | Fully refunded when outbid |
| `iddeployertest.testnet` | 1.5 test NEAR | Winning amount; NFT delivered |

Total bid principal: **3.8 test NEAR**. Successful automatic refunds total
**2.3 test NEAR**, leaving the **1.5 test NEAR** winning payment. Each account's
sum of bids minus its successful refunds equals its expected final cost: 1.5
for the winner and zero bid principal retained from the losing wallet.
Gas and one-time bidder registration are separate from bid principal.

Finalized bid transactions and successful refund callbacks were read directly
from the RPC. The 1 NEAR refund appears in transaction
`GLiVbe7hBvxjNePi5xbx8M9BGrcsuziiU4izjGFrAJh1`; the 1.3 NEAR refund appears in
`CJD7t3tRxyZjMgmBeNn65mF7Fu7mmpNQLMgNCdxiuMqk`. Both auction `claim` events
report `success: true`. Refunds occurred on outbid, before finalization.

Settlement transaction: `2rfusNsmqjuX7qVHUkAFDbhTvPg3F8fywc8Z4biukmZu`.
Vault funding transaction: `EVyPfQvg1frXbkgyzNGJMgSwy1se92pDoRgdUGEEdkdQ`.
Treasury payment transaction: `Ae7wLLasAHAGZGGXQvEDPNAhuqWokoU2XRqz5kKMEHb3`.

The running site reports Settled, Funded and the winning owner. Detailed before/
after snapshots, accounting assertions and journals remain in the ignored lab
workspace; credentials and private replay state are excluded from the repository.

## Remaining acceptance

The winner can inspect the NFT in My collection and use it for marketplace or
owner-rights tests. Secondary purchases/offers and holder fees, a no-bid auction,
early exit, monthly collection/draw/rollover and holder royalty distribution
remain to be exercised. No withdrawal or month-end draw was performed here.
Use the [testnet runbook](../TESTNET_LAB.md) for those steps. The known historical
draw entropy and synthetic edition are test-only; independent review and
managed-cloud/mainnet commissioning remain outstanding.
