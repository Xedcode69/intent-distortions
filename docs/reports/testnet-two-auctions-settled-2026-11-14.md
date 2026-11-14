# Two winning auctions settled — 14 November 2026

The two remaining auctions were ended and settled on public NEAR testnet.
The isolated contract clock advanced from January 3 to January 4, 2027 at
00:00 UTC, exactly their deadline. These are controlled test dates, not the
calendar date of this report. No new bid, marketplace trade, withdrawal or
monthly draw was submitted by this operator run.

| NFT | Winning bid | Confirmed owner | Treasury 20% | Funded edition wallet 80% |
|---|---:|---|---:|---:|
| ECHO-000007 | 1.3 NEAR | `idtester1.testnet` | 0.26 NEAR | 1.04 NEAR |
| ECHO-000008 | 1.1 NEAR | `idtester1.testnet` | 0.22 NEAR | 0.88 NEAR |
| Total | 2.4 NEAR | Both NFTs delivered | 0.48 NEAR | 1.92 NEAR |

Both auctions report `Settled`, and fresh canonical NFT views match the actual
highest bidder. Their dedicated accounts are `Funded`; original, remaining and
vault-available amounts agree exactly with the table. Storage/operating reserves
are separate from those economic allocations. Both beneficiaries match the NFT
owner, cycle `202701`, with no exit, collection or pending transfer. Edition 7's
account remains `december2026-edition-4.id-nft.testnet`, named for its scheduled
release; its auction settled in January. Edition 8 uses
`january2027-edition-1.id-nft.testnet`.

The treasury's native balance increased by exactly 0.48 NEAR. NFT coordinator
gross/treasury counters increased by 2.4/0.48 NEAR. Pending treasury payment,
treasury credit and coordinator financial liability are all zero after delivery.
The earlier December edition's 1.2 NEAR allocation was preserved. Monthly
`next_close` remains `202612`; the earlier December draw was deliberately not
run during this auction-only test.

## Final receipts

| Operation | Verified FINAL transaction |
|---|---|
| Settle ECHO-000007 | [FYULV4rD2eWqQBHBT1VsU8rouMaW6VoqPWAAt7Bvatu1](https://testnet.nearblocks.io/txns/FYULV4rD2eWqQBHBT1VsU8rouMaW6VoqPWAAt7Bvatu1) |
| Fund its edition wallet | [4cnhaL9Dd451A2TZ3zhurxCj9G2bkHVQwNbX8brq1JhS](https://testnet.nearblocks.io/txns/4cnhaL9Dd451A2TZ3zhurxCj9G2bkHVQwNbX8brq1JhS) |
| Settle ECHO-000008 | [7Rh6bryJ2Mah6Dpy3NMKFHFFv8hdKQBiAW3Cd14hzYVj](https://testnet.nearblocks.io/txns/7Rh6bryJ2Mah6Dpy3NMKFHFFv8hdKQBiAW3Cd14hzYVj) |
| Fund its edition wallet | [Bam9ymh7kSPhzTkPq9zNr34ExKci9fcXUyYVsGLB3WYc](https://testnet.nearblocks.io/txns/Bam9ymh7kSPhzTkPq9zNr34ExKci9fcXUyYVsGLB3WYc) |
| Deliver treasury credit | [3LE2WZYQiUn6tnay82LCrwaEKiR7Ft74FGLQGRyPUqQT](https://testnet.nearblocks.io/txns/3LE2WZYQiUn6tnay82LCrwaEKiR7Ft74FGLQGRyPUqQT) |

Each operator receipt was checked for the expected signer, receiver, method,
arguments, deposit and FINAL result, including descendant execution failures.
Contract identity/code/policy checks preceded the operation. The explicit
rehearsal calls use the same contract maintenance methods used by the production
keeper; this does not claim a managed-cloud worker was running on this laptop.

## Bid refund

The earlier 1 NEAR bid on edition 8 from `iddeployertest.testnet` was fully
refunded when `idtester1.testnet` bid 1.1 NEAR. Its exact native-transfer receipt
`7jxRW1rfkqYdiWKkjxDv8k7i6F3p7dnGwrwHnRGZ7Wp8` was fetched and checked:
predecessor `id-auction.testnet`, receiver `iddeployertest.testnet`, amount
`1000000000000000000000000` yoctoNEAR, successful execution. It belongs to the
[outbidding transaction](https://testnet.nearblocks.io/txns/AizeXVe6dig3b8v8WWgxsvEHLbSQab2wvj7gbx5t14U1).
Both registered bidders now have zero outstanding refund credit. This verifies
bid principal; transaction gas and the retained registration storage are not
refund principal. The local receipt index remains a partial history, so no
complete network-wide bid-history coverage is claimed.

## Site verification

Read-only checks through the local frontend proxy confirm six minted NFTs,
zero active auctions, three sold primary auctions and the earlier two no-bid
returns. The winner's owned collection contains editions 7 and 8 and their
funded detail views agree with the chain. Marketplace, My collection and both
auction routes respond successfully. The site is restarted at
http://127.0.0.1:3004. No application code or contract code needed changing.
Browser visual/wallet acceptance and the separate marketplace/monthly reward
scenarios remain distinct tests; no mainnet operation occurred.
