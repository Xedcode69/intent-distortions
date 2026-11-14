# Marketplace and collection royalties

`/marketplace` is a secondary marketplace for the canonical Intent Distortions NFT contract. Listings and escrowed offers are denominated and settled in native NEAR. Successful secondary sales pay **95% to the seller and 5% to the collection royalty pool**. This is independent of the primary auction's 20% treasury / 80% edition-vault allocation. Resales do not refill the edition vault or create additional raffle tickets.

## Listings and offers

The collection page shows collection totals and the lowest active fixed price,
then a single artwork grid with valid listings first. Search, status, art-family
and connected-owner filters apply to the complete finalized collection before
pagination. Stats exclude expired/revoked listings and pending sales; offers-only
listings count as listed but do not set a floor. All snapshot queries use one
finalized block and verify the enumerated NFT supply. The snapshot cache lasts
ten seconds; action checks always read fresh contract state.

Click an artwork in the market or **My collection** to see its image, traits,
owner, offers and edition wallet. Owners can list/update a price, open to offers,
cancel a listing, transfer or review an eligible early withdrawal there. The
withdrawal requires a separate confirmation explaining the exact 40% payment,
60% rollover and loss of the funded month's draw ticket. Rewards remains the
collection-wide financial overview.

**One button runs required setup and the action in order.** List, Buy and Place
offer first check current ownership, listing and financial rights, top up market
storage when needed, then recheck before requesting the action. A wallet may
still show two approvals. Cancelling setup stops the action; account/rights/price
changes require fresh review. Cancellation removes the listing and then revokes
approval from the same button. NFT approval itself creates the listing through
its NEP-178 callback. An update reuses its existing record storage. As the current
balance view does not distinguish an unused registration from an absent one,
a zero-storage buy conservatively attaches 0.01 NEAR to setup; on an already
registered account this becomes recoverable storage credit.

Offers can be filtered across the complete offer set as made/received by the
connected account. Offers require an active priced or offers-only listing.
Cancelled offers and sale proceeds are withdrawn from Wallet & balances; these
are separate choices from approval/setup, so they are not silently spent or
withdrawn as part of another action.

The owner registers storage on `echo-market`, then approves it through NEP-178 `nft_approve` with a price and expiry. A null price enables offers without a fixed-price purchase. Listings last at most 30 days (the UI uses seven). The NFT stays with its owner while listed, preserving its financial rights. Reapproval creates a new listing nonce. Only the fixed canonical NFT contract can create a listing callback; primary auction custody cannot list.

Buyers register storage, then attach the exact listing price plus one yocto to `buy`. Offers escrow the offered amount plus one yocto, bind to the seller/listing nonce and expire no later than the listing (the UI caps them at 24 hours). The seller can accept an active offer. The buyer can cancel an unused offer at any time; anyone can release it after expiry. Unselected offers remain individually refundable after another sale or a listing cancellation; they are never consumed by that sale.

The market reserves a sale before the asynchronous NFT transfer. The NFT atomically checks the expected owner, NEP-178 approval ID and the financial-state hash reviewed by the buyer. A withdrawal, collection, funded cutoff, pending transfer or ownership change invalidates an outdated financial snapshot. A failed transfer returns the entire sale amount as buyer credit and charges no royalty. A failed offer acceptance consumes that offer and returns its full amount as refundable credit. Successful sales credit the seller's 95%; withdrawals debit first and restore credit on failed delivery. There is no administrator sweep method and the worker cannot sign purchases, offers or credit withdrawals.

The initial storage registration retains 0.01 NEAR to cover the account record. Each active listing/offer reserves 0.01 NEAR, released when its record is removed. `withdraw_storage` returns unused storage plus any credit; registration remains. NFT approval storage is separate and its surplus is refunded by NEP-178. The additional one-yocto attachments cover authorization/transfer plumbing. Operators separately fund contract code and continuing storage; royalty funds are liabilities, not an operating budget.

## Monthly holder royalties

Each eligible NFT in the **entire minted collection** earns one equal share at the UTC month-end cutoff. Three eligible NFTs in one wallet earn three shares. Creator/team-held NFTs and protocol custody accounts (NFT contract, primary auction and marketplace) are excluded. Creator-origin editions, NFTs that used their early withdrawal and NFTs whose original raffle already ended are eligible when held by a collector. Royalties are independent of vault funding and raffle eligibility.

The NFT records permanent monthly ownership checkpoints at mint and finalized transfer. Multiple transfers in one month overwrite that month's latest checkpoint; later months append a checkpoint. A transfer exactly at the next month's midnight belongs to the new month. A pending `nft_transfer_call` does not change the last finalized owner until its resolver completes. These on-chain checkpoints let a delayed keeper reconstruct an old cutoff without trusting a database, indexer or ownership oracle.

The fee is `floor(gross / 20)` in yoctoNEAR. Its royalty month is fixed when the marketplace reserves the sale; that month cannot close while a sale callback is pending. After cutoff, `prepare_royalties` processes at most 25 NFT ownership records per call. Only NFTs minted before cutoff are eligible. The first batch fixes the enumerated supply, and subsequent batches cannot add later mints or duplicate shares. Months close sequentially, starting with the marketplace's deployment month.

Once all records are processed, each eligible NFT receives `floor(pool / eligible_count)`. Rounding dust rolls into the next month. With no eligible holders, the entire pool rolls forward. An earned entitlement stays with the cutoff owner after a resale. `pay_royalty` delivers to that fixed account, records Pending before dispatch and restores a retryable payment on failure. Payments remain claimable/deliverable without an expiry. No owner can redirect another person's payment. The deterministic keeper prepares batches and delivers/retries payments automatically; anyone can perform the same calls. This requires the worker to be running with its reviewed signing policy and sufficient gas/storage reserves.

This royalty is enforced on sales **through this marketplace**. Standard direct NFT transfers and external marketplaces cannot be forced to pay it. NEP-199 interoperability is not claimed.

## Cross-chain checkout with NEAR Intents

The integration uses the official [1Click funding flow](https://docs.near-intents.org/integration/distribution-channels/1click-api/quickstart/making-a-request) and [EXACT_OUTPUT quotes](https://docs.near-intents.org/integration/distribution-channels/1click-api/swap-types). A buyer connects an existing NEAR account for NFT ownership, selects a currently supported source-chain token and supplies their own source-chain refund address. The backend fixes the destination to `nep141:wrap.near`, `recipientType: DESTINATION_CHAIN`, and the connected buyer account. It never routes funds directly to a seller or the marketplace and accepts no custom recipient message. A live listing's price (or the requested offer) plus **0.1 NEAR** for registration/storage/gas determines the requested output. Unused funds belong to the buyer.

The UI first previews a dry quote, then explicitly creates deposit instructions. It preserves the source deposit address, required memo, maximum source amount and deadline. The buyer sends funds using their source wallet and checks 1Click status. After settlement, they check their NEAR balance and, if necessary, authorize `near_withdraw` on the official wrapper to unwrap received wNEAR. Unwrapping requires native gas. They then review the live price/financial state and explicitly authorize `buy` or `make_offer` in their NEAR wallet.

This is **funding followed by purchase**, not an atomic cross-chain NFT exchange. The NFT is not reserved while the swap runs. If the listing changes, expires or sells, the converted funds remain in the buyer's wallet. Failed/underfunded/late swaps follow 1Click's source-chain refund rules; a successful conversion is not automatically reversed because the NFT becomes unavailable. Source-wallet deposit signing is performed by the user's wallet, not the backend. A `SUCCESS` swap status never proves NFT delivery; ownership must be read from the NFT contract.

The feature is disabled in replay/demo and testnet. Enable it only on reviewed mainnet deployments with `MARKETPLACE_CROSSCHAIN_ENABLED=true`. The optional `NEAR_INTENTS_1CLICK_JWT` belongs to the **API service** and should be a Distribution Channel key. It is separate from the worker's Explorer key (`NEAR_INTENTS_PARTNER_JWT`). Unauthenticated quotes are possible with the provider's additional fees; the actual quote determines the amount. Keys never enter frontend bundles. See the official [authentication guide](https://docs.near-intents.org/integration/distribution-channels/1click-api/authentication).

## Deployment and local testing

Build all four contracts using `uv run --locked python scripts/build_contracts.py --test`. Initialize a separately funded marketplace account with `new({nft_contract, primary_auction, creator})`. Configure `NEAR_MARKET_CONTRACT` and pin `EXPECTED_MARKET_CODE_HASH` in API and worker environments. The NFT must advertise both `echo-market-transfer-v1` and `monthly-finalized-owner-v1`; pin the new NFT WASM as well. Preflight checks addresses, 500 bps fee, creator exclusion policy, network and deployed hashes. Set the marketplace creator to the same `NEAR_CREATOR_ACCOUNT` used by the NFT economy.

**NFT state layout changed** to add ownership history. This candidate requires a fresh NFT deployment or a separately reviewed migration; deploying its WASM over an older NFT state without migration is unsupported. There is no automatic migration and no retroactive historical ownership evidence for old live NFTs. No real-network deployment is authorized or performed by these changes.

On Windows, `scripts/test_economy_sandbox.ps1` runs the built production WASM in a disposable NEAR 2.14 sandbox. The historical `/demo` remains read-only and includes an explicitly illustrative royalty simulator. No fake marketplace listings, offers or royalty balances are presented as live state. Live cross-chain settlement, wallet UX and independent contract review remain release acceptance work.

See the [marketplace validation report](reports/2026-11-13-marketplace-validation.md) for test evidence and current WASM hashes.
