# Current API

Public application routes use `/api/v1`. The Next.js server proxies the same prefix and keeps provider credentials private. `/readyz` is the backend hosting health check.

| Route | Meaning |
| --- | --- |
| `GET /health`, `/protocol` | Public testnet configuration, automation state and policy commitment. |
| `GET /artworks`, `/artworks/latest`, `/artworks/{id}` | Saved weekly editions plus the preserved `genesis`. |
| `GET /artworks/{id}/traits`, `/artworks/{id}/verify` | Frozen attributes and integrity verification. |
| `GET /drops` | Upcoming release, persisted capture/generation stages and archive lifecycle. |
| `GET /onchain/prototype` | Pinned genesis contract/owner/commitments. |
| `GET /onchain/prototype/static.svg`, `/animated.svg`, `/recipe.bin` | Hash-verified genesis bytes, recovered from NEAR. |
| `GET /onchain/editions/{token}/{asset}` | Frozen weekly static.svg, animated.svg, recipe.bin or provenance.json. |
| `GET /wallets/{account}/collection` | Current ownership in the weekly collection; genesis ownership is read separately. |
| `GET /auctions`, `/auctions/{artwork-id}` | Finalized contract auction state. |
| `GET /marketplace`, `/marketplace/collection`, `/marketplace/offers` | Configuration, collection/filter results, offers. |
| `GET /economy`, `/economy/months`, `/economy/wallets/{token}` | Economic rules, monthly state and per-edition financial rights. |
| `POST /receipts` | Validate/index a submitted finalized contract receipt. |
| `POST /verify/merkle-proof`, `/verify/block-selection` | Recompute supplied membership/selection evidence. |

Wallet-authorized transactions perform bids, sales, offers, withdrawals and claims. Backend endpoints do not sign user purchases. The constrained worker signs scheduled publication and permissionless maintenance only when explicitly enabled. Cross-chain funding endpoints are disabled.

Raw source captures, cursors, API keys and signed journals are never returned in drop progress. Live content reads allow only public source-preview/scene files; canonical minted media comes from the onchain endpoints. Hash verification does not prove source completeness or ownership. Lists accept bounded pagination; cached chain snapshots may lag by a short refresh interval.

Legacy replay/lab endpoints and synthetic fixture generation are development tools. Hosted routes exclude demo mutation; the frontend proxy excludes demo/admin paths. Read the README and managed-cloud.md for the one shipped testnet profile.
