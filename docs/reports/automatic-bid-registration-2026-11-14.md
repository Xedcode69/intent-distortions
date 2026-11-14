# Automatic bidder registration — 14 November 2026

The live failed bid came from an unregistered wallet. `place_bid` rejects that
condition before accepting a bid; the deployed WASM reports its assertion as a
generic unreachable-opcode trap. The transaction's failure and the wallet's
unregistered state were read from public testnet receipts and contract views.

The auction page now has one **Place bid** action. It checks the connected
wallet's registration and current auction before asking for approval. A first-time
bidder approves the 0.01 NEAR registration, waits for confirmation and then
approves the exact entered bid. A registered bidder gets only the bid approval.
The page displays the first-bid fee and two-approval notice; there is no separate
registration button.

The flow stops if registration is cancelled, fails or cannot be verified. It
rechecks account identity, custody, the auction deadline and the minimum before
the bid; it never raises the entered amount automatically. Account switching
requires review. Registration remains reusable if the subsequent bid is declined.
Refund claims and settlement controls appear when relevant.

The new read-only bidder endpoint returns registration and refund state for the
requested account. Invalid or unavailable RPC responses do not become an inferred
unregistered state. The private lab profile now uses the verified regular testnet
RPC for current-state queries rather than the throttled archival endpoint.
Deployed contract code and auction state were not changed by this update.

Validation:

- **183 backend tests passed**, 1 PostgreSQL test skipped; existing AnyIO warning.
- **26 Node tests passed**, including first/subsequent bids, cancellation,
  unconfirmed registration, account changes, expiry and a changed minimum.
- Frontend production build and TypeScript passed.
- The running site's health, bidder-state and auction endpoints returned HTTP
  200; lab readiness and Active/custody-verified auction state were confirmed.
- The auction page returned HTTP 200. Browser wallet approvals for this new
  two-transaction sequence remain to be accepted by the tester.

Reload `http://127.0.0.1:3004/auction/demo-000004`, enter the bid and click Place
bid. Confirm registration first if prompted, then confirm the bid.
