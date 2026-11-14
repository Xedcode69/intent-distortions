# Initial public testnet deployment — 14 November 2026

The lab contracts were deployed to NEAR testnet and checked against the reviewed
WASM hashes and financial policies. This is initial acceptance, not a completed
auction/marketplace/rewards test or a mainnet deployment.

| Role | Testnet account |
| --- | --- |
| Governance | `id-deployer.testnet` |
| Operator | `id-operator.testnet` |
| Team | `id-team.testnet` |
| Treasury | `id-treasury.testnet` |
| NFT/factory | `id-nft.testnet` |
| Auction | `id-auction.testnet` |
| Marketplace | `id-marketplace.testnet` |

Contract pins are unchanged from the [reviewed lab build](testnet-lab-2026-11-14.md).
The operator and contract accounts' keychain public keys were matched against
their onchain full-access keys. Only public-key information was queried.
All 36 public artwork files matched their prepared hashes before deployment.
The private profile's missing HTTPS scheme was corrected; the unresponsive
default RPC was replaced with the verified testnet endpoint used by NEAR CLI.

## Verified starting state

- Historical genesis `ECHO-000001` is owned by `id-team.testnet`. Its canonical
  image hash remains `8fec6c77137badb4cd124b8235287eb36ab902ebbb0f27e6b78829dd47af8fca`.
- Its dedicated account is `november2026-edition-1.id-nft.testnet`.
- Synthetic fixture `ECHO-000004` is in `id-auction.testnet` custody, with an
  **Active**, custody-verified auction. Minimum bid: 1 test NEAR; increment: 0.1.
- Its dedicated account is `december2026-edition-1.id-nft.testnet`.
- Both edition accounts are Ready and keyless, with the pinned vault code and
  NFT controller. Initial unfunded vaults have no raffle allocation.
- All three lab clocks agree at **2026-12-06 00:00 UTC**. The auction ends at
  **2026-12-07 00:00 UTC** on that controlled clock; it does not count down in real time.
- `/api/v1/health` reports the configured contracts and `lab_ready: true`.
  Marketplace configuration reports native NEAR settlement and the 5% fee.

The local site is `http://127.0.0.1:3004`; use `/my-collection`,
`/auction/demo-000004`, `/marketplace` and `/economy` for wallet testing.
Detailed local snapshots and the signing journal remain in the ignored lab
workspace. Credentials, raw captures and private workspace files are not published.

## Live issues corrected

The launcher previously polled network-dependent health with a one-second
timeout. It now probes local `/readyz`; contract health uses one bounded,
deduplicated set of public reads. RPC errors disable actions.

The first auction activation correctly failed because its edition account had
not yet reached Ready. The keeper now completes factory receipts before auction
activation, checks economic eligibility, retries failed custody where eligible,
and verifies Active/custody-confirmed state after the callback. Recovery used
the existing contract method; no contract code was changed or auction recreated.
Successful recovery transaction:
`CdYAzjsrvhUuwEVm2DtSEqW94mhv6thxCcW4M1Miq874`.

Regression validation: **175 backend tests passed, 1 PostgreSQL test skipped**;
the existing AnyIO deprecation remains. New tests cover deduplicated/fresh reads,
timeout and operator-lock behavior, factory-before-activation ordering, custody
recovery and rejection of an unsuccessful activation callback. Local HTTP checks
verify the configured health, market policy, auction state and edition accounts.

## Next acceptance steps

Use two funded collector testnet wallets: register bidder storage, bid 1 NEAR,
then outbid with at least 1.1 NEAR. Verify the losing bidder's refund. Advance
the lab clock only after bids are placed, then run the keeper to settle and fund
the vault. Test genesis resales/offers through the team wallet, early exit,
month-end pot collection/draw/rollover and holder royalties using the remaining
fixtures in the [runbook](../TESTNET_LAB.md).

Those financial outcomes and browser wallet acceptance remain outstanding.
Known historical draw entropy and synthetic auction data are test-only. Live
1Click cross-chain settlement is disabled in this lab and needs separate mainnet
acceptance. Managed-cloud rollout and independent review remain outstanding.
