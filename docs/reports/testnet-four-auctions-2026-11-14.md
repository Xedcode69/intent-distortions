# Four-artwork auction rehearsal — 14 November 2026

All four remaining synthetic test artworks were minted from their verified,
publicly hosted frozen packages. Their dedicated accounts were created and
verified keyless with the pinned vault code. No bidder transaction was signed
by the operator for this run.

| NFT | Verified outcome | Current owner | Auction receipt |
|---|---|---|---|
| ECHO-000005 | No bids; finalized `Unsold` | `id-team.testnet` | [Settlement](https://testnet.nearblocks.io/txns/AKFSwyJkShuKxWi4JrAPtJPCZ9Dww6edizM8QCdSJkVG) |
| ECHO-000006 | No bids; finalized `Unsold` | `id-team.testnet` | [Settlement](https://testnet.nearblocks.io/txns/CiopaAWKfVqqfcQpBok6Z93mD7CuypzEtfELvVAuqYcr) |
| ECHO-000007 | Active, verified auction custody, zero bids | `id-auction.testnet` | [Creation](https://testnet.nearblocks.io/txns/Cno7ZJXEMdwmZXbp331oKrVYJGo3vuEfh7kbF95Qj2mV) |
| ECHO-000008 | Active, verified auction custody, zero bids | `id-auction.testnet` | [Creation](https://testnet.nearblocks.io/txns/7hnQa1SzVqD2CyKdaGkagMngpSbTcXpsRYEiou6gFSVA) |

The no-bid outcomes were verified from FINAL cross-contract receipts and fresh
NFT ownership/auction views. Both have `highest_bid = 0`, no highest bidder,
`cycle = null`, and original/remaining allocation zero. They create no funded
raffle ticket. No transfer to a collector, primary-sale treasury allocation or
raffle funding was inferred from an auction-status label alone.

Dedicated accounts:

- ECHO-000005: `december2026-edition-2.id-nft.testnet`
- ECHO-000006: `december2026-edition-3.id-nft.testnet`
- ECHO-000007: `december2026-edition-4.id-nft.testnet`
- ECHO-000008: `january2027-edition-1.id-nft.testnet`

The isolated clock is frozen at **3 January 2027, 00:00 UTC**. The two open
auctions end at **4 January 2027, 00:00 UTC**, each with a 1 NEAR initial minimum
and 0.1 NEAR increment. They remain open until the lab clock is advanced.
Both first auctions started on virtual December 20 and ended December 21;
the second pair started only after the no-bid returns were verified. The clock
cannot be rewound. Earlier December listing expiries and withdrawal cutoffs
have passed. No monthly close, draw, prize, royalty payment or collector exit
was run as part of this auction-only rehearsal. Existing edition 4's settled
sale and 1.2 NEAR December allocation were preserved.

## Collection interface and rehearsal fix

The market displays counts and filters for **On auction**, **Sold** (completed
primary auctions) and **No bids / returned**. Active cards link directly to the
correct artwork's bidding page and show the current bid or initial minimum.
Sold cards show their verified primary price; returned cards show the team
return only while the current owner is the configured team. Item details also
link auction custody to the primary auction rather than offering a secondary
purchase from the auction contract.

These states are read from the auction and NFT contracts at the same finalized
block as the rest of the collection. Active status additionally requires
verified custody, current auction ownership and an unexpired deadline. Sold
requires positive bids and completed settlement; expired Active, failed custody
and pending funding are not presented as active/sold. Filters apply before
pagination. Production and testnet share this interface.

The testnet tool's wallet-creation journal key now includes the token ID;
previous editions' completed first attempts no longer collide. A regression
test preserves the earlier journal entry and verifies a later account operation
uses its own key. One initial read-only clock/policy timeout occurred before
mint submission; current state was checked and policy reads were deduplicated
within each locked operator action. No unknown payment was blindly repeated.

Validation: 200 backend tests passed (one PostgreSQL integration skipped),
35 JavaScript tests passed and the production Next.js build/TypeScript passed.
Final focused collection/journal tests cover the completed source changes.
Live HTTP/API checks confirm six minted NFTs: two open auctions, one previously
sold primary auction and two verified no-bid returns. Bidding routes for editions
7 and 8 return successfully. Browser visual/wallet bid acceptance remains with
the user. No mainnet operation or contract-code deployment occurred.
