# Collection market and production automation — 14 November 2026

The market now has an original collection header, live collection statistics,
filters, listed-first artwork cards and an Offers tab. My collection uses the
same bounded square card layout without the gallery's staggered/inline-link
rules that caused clipping and overlapping captions. Clicking a card opens an
accessible native dialog with trading, ownership, frozen traits and edition funds.
No external marketplace code, screenshots or visual assets were copied.

Listed status requires a live deadline, current seller ownership, the current
NFT approval and no pending sale. Server-side collection ordering/filtering
precedes pagination, using one finalized block, complete enumeration and a supply
check. Offers can be filtered across the entire bounded offer set by token,
made offers or received offers. Query limits fail closed instead of returning
misleading partial collection totals.

Buy/List/Place offer now prepare required marketplace storage and request the
action from one button. Wallet approvals remain distinct transactions. Wallet
identity and current listing/financial rights are rechecked between steps;
cancellation or an unconfirmed setup stops the sequence. Listing approval uses
the NFT's existing listing callback. Cancel listing also revokes NFT approval
after cancellation confirms. Sale proceeds/cancelled offers remain explicitly
withdrawable marketplace credit; no unrelated balance is silently spent.

Owner-specific early withdrawal is inside the artwork detail view, with a
confirmation of its exact amount, loss of the draw ticket and next-month
rollover. Only the current owner of a funded, unexited, uncollected edition can
use it before the UTC cutoff. Fresh ownership/rights checks run before signing;
the contract independently enforces these rules. The Rewards page remains the
aggregate financial overview and links to artwork controls.

Production and testnet use these same components and helpers. The production
worker now services maintenance before release work and during long Explorer
captures, requests only SUCCESS records, verifies the historical block source
network, and leaves v3 settlement to the economy keeper. Capture can run while
maintenance works; signing remains serialized under the existing PostgreSQL
lease. Ambiguous signed outcomes stop progression. The managed blueprint asks
for marketplace account/hash configuration. Production preflight omits the
Explorer test-record flag rather than passing a value interpreted as enabled.
Scheduled production mints now use the testnet-rehearsed 1 NEAR storage deposit
instead of 0.1 NEAR, accommodating expanded trait metadata. The isolated signer
permits that cap only for scheduled minting; other deposit limits and the
financial-method allowlist remain enforced. NFT storage surplus is refunded;
edition-account operating reserves remain a separately funded requirement.

## Validation

- Production Next.js build and strict TypeScript compilation passed.
- Final backend suite: 192 passed, one PostgreSQL integration skipped in this
  run. Two additional collection enumeration/offer-pagination cases passed in
  the subsequent focused collection run (five collection tests passed).
- JavaScript suite: 31 passed, including stopped flows after cancellation,
  wallet/rights changes, insufficient confirmed storage and exact withdrawal math.
- Targeted collection/maintenance/worker/market tests: 24 passed after final
  source-RPC and minted-supply changes. The existing AnyIO deprecation remains.
- Production publication tests verify the 1 NEAR scheduled-mint deposit and
  that mismatched public artifact bytes stop publication before any signing.
  Signer tests verify the new mint cap and unchanged caps on other methods.
- Deployment schema and source/binary separation checks passed.
- Read-only local testnet check through the frontend proxy passed: two minted
  NFTs, two owners, Crystalline and Fractal branches, zero active listings and
  no invented floor. Owner filters, owned-wallet queries, offers filtering and
  market/My collection/Rewards/Drops HTTP routes passed. No transactions signed.

The updated site runs at http://127.0.0.1:3004. This is the isolated testnet lab;
it has no background signer. Production automation requires its separately
deployed worker, database, provider credentials, funded operating reserves and
explicit signing configuration. Mainnet writes remain disabled in the template.
The managed production and testnet ZIPs are rebuilt from the shared source with
their separate unchanged WASM sets; the educational demo remains separate.

Browser visual/wallet QA was blocked because the computer-use tool could not
verify the current Chrome URL. It was stopped, with no browser-automation
fallback. Builds/API tests do not establish visual/mobile acceptance or real
secondary trades, withdrawal, monthly draw, mainnet cross-chain checkout or
managed-cloud operation. Those financial/deployment acceptance checks and the
independent contract review remain outstanding. No mainnet deployment occurred.
