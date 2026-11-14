# Monthly rewards, drop badges and transaction links — 14 November 2026

Rewards is now a monthly overview. It no longer renders each NFT's wallet,
beneficiary or individual balance, and no longer polls a separate endpoint for
each NFT. The current month appears first, then upcoming rollover cycles and
previous cycles. Each card shows eligible draw funds, eligible artwork count,
early-withdrawal count, incoming rollover and the amount reserved for the next
month's draw. A winner/payment result appears only when a draw exists. Owner
controls remain under the artwork in My collection.

`GET /api/v1/economy/cycles` aggregates the complete bounded wallet/month sets
at one finalized block and verifies the NFT code hash, network and clock-build
boundary. All amounts use integer yoctoNEAR arithmetic. It includes funded
eligible allocations still held in edition wallets, distinguishes pending
funding, adds incoming rollover once, and avoids counting collected funds again.
Accepted early exits remove their original month's ticket; their remainder
contributes funds to the following month without a new ticket. Historical
rollover is derived from the original allocation so collection's zeroed remaining
balance does not erase it. Empty-draw carry and early-exit rollover are disjoint.
Closed draws retain their frozen entry count and final prize amount.

Totals refresh every 30 seconds. Refresh requests bypass the ten-second shared
snapshot cache. Pending collections and incoming rollover transfers are identified concisely. Projected
rollover into a not-yet-created contract month is marked Upcoming rather than
presented as an existing on-chain pot. No new early withdrawal or draw was sent
to demonstrate these changes; financial state-change cases are covered by tests.

Live read-only checks after the two recent auction settlements show:

| Cycle | Eligible draw funds | Eligible artworks | Early withdrawals | Next-month rollover |
|---|---:|---:|---:|---:|
| January 2027 | 1.92 NEAR | 2 | 0 | 0 NEAR |
| December 2026 | 1.2 NEAR | 1 | 0 | 0 NEAR |

December is Awaiting close on the frozen January 4 lab clock. Its draw was not
run during the auction settlement check. The amounts above are allocated draw
funds, including uncollected edition-wallet balances, not a claim that the
coordinator has already pooled them.

## Drops and marketplace

Past distortions now marks On auction, Sold and Reserved from a verified
collection snapshot. Reserved means the configured team currently owns the NFT;
this takes precedence if the team later reacquires a previously sold artwork.
Image commitments must match before a badge is attached. Saved artwork labels
or a failed chain read cannot fabricate a Reserved/Sold badge. Recorded NFT
release dates correct synthetic fixture archive dates without modifying art,
seed, image or provenance. The mint-only rehearsal still serves its saved
history when no marketplace is configured, without ownership badges.

The current testnet archive has three Sold and three Reserved artworks. Those
lifecycle badges/prices are removed from marketplace cards; marketplace status
filters remain. Secondary Listed/Open to offers and Yours labels remain useful
trading information. Active primary cards retain a link to their bidding page.
Drops checks active creation every five seconds and finished drops every thirty;
the shared ownership snapshot is reused for up to thirty seconds to reduce RPC
pressure.

## Auction and transaction UI

The auction heading uses JSX line breaks, eliminating the literal `<br/>` text.
Creator editions, active bidding, settled sales and no-bid endings have distinct
headings/content. Ended auctions no longer show an active bid form. Curatorial
controls are limited to the artwork being viewed.

All wallet action confirmations now display clickable full NearBlocks URLs for
the correct network. Multi-step registration/listing flows retain a link for
each successful transaction even if a later approval is cancelled. Known failed
transaction results retain an explorer link; ambiguous results are not marked
confirmed or automatically resubmitted. Hash/network validation and React text
escaping prevent injected explorer destinations. Auction bids/refunds, NFT
trading/ownership controls, credit/storage tools, owner curation and retryable
monthly prize delivery use the shared link UI.

## Validation

The production frontend build and TypeScript pass. Backend tests: 210 passed,
one PostgreSQL integration skipped. JavaScript tests: 37 passed.
Backend tests cover monthly funding/exits, frozen tickets, pending allocations,
carry, no double counting, forced refresh, contract identity, and current-owner
drop badges. Read-only checks pass for Rewards/Drops/marketplace and creator/
settled-auction routes. The testnet site is running at http://127.0.0.1:3004.
Browser visual/wallet signing QA was not performed; no extra transaction was
sent merely to preview a confirmation. Production and testnet source bundles
are rebuilt from the shared code with their separate unchanged contract sets.
