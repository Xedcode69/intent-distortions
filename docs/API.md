# API v1

Interactive schema: `/docs` in development; docs and demo routes are disabled in production. Routes below start with `/api/v1`; database readiness is separately available at `/readyz`.

The main frontend's `/demo` page is a separate read-only historical showcase backed by prepared static public assets. It does not use the development-only `/api/v1/demo/*` generation endpoints and is available in the production frontend without enabling those endpoints.

Local historical mode additionally exposes `GET /api/v1/replay/progress`: allowlisted phase, interval, received rows, pages, elapsed time and completed capture counts. The total and collection percentage remain null until pagination completes; completed collection reports 100 independently of later artwork verification. Production and other execution modes return 404. The route reads no integration credentials and has no write operation.

| Resource | Routes |
|---|---|
| Health/configuration | `GET /health`, `/protocol` (no secret values) |
| Epochs | `GET /epochs`, `/epochs/current`, `/epochs/{id}`, `/epochs/{id}/statistics`, `/epochs/{id}/provenance` |
| Artworks | `GET /artworks`, `/artworks/latest`, `/artworks/{id}`, `/artworks/{id}/dna`, `/artworks/{id}/manifest`, `/artworks/{id}/verify`, `/artworks/{id}/traits` |
| Files | `GET /content/{sha256}`; local byte validation or production redirect to the immutable artifact CDN |
| Auctions | `GET /auctions`, `/auctions/active`, `/auctions/{edition-id}`, `/auctions/{edition-id}/bids` |
| Analytics | `GET /analytics/summary`, `/analytics/chain-distribution`, `/analytics/weekly-activity`, `/analytics/treasury` |
| Verification | `POST /verify/block-selection`, `/verify/merkle-proof`, `/verify/artwork` |
| Demo | `POST /demo/run-epoch`, `GET /demo/status` |
| Operations | `GET /admin/jobs`, `/admin/releases` with bearer `ADMIN_TOKEN` over the private network |
| Receipt indexing | `POST /receipts` with transaction hash/sender; independently verified against finalized configured-contract outcomes |

Block verification input: `{ "epoch":1, "sunday_start":1794096000, "beacon":{...} }`. The signature and scheduled round are recomputed. This endpoint returns the selected timestamp; block/finality checking is a separate archival RPC operation.

Merkle input: `{ "record":{...}, "proof":[{"hash":"64 hex","side":"left"}], "root":"64 hex" }`. Artwork input: `{ "id":"demo-000001", "rerender":true }`.

Demo generation is restricted to development/demo configuration, loopback clients and allowed browser origins. Repeated runs return existing frozen state. There is deliberately no public reset route; use a new disposable local demo database for a separate experiment. Production editions must never be reset.

No backend endpoint submits user bids. All bids/claims use a wallet-authorized contract transaction. Auction views query finalized onchain state. The bid-history route returns only successful indexed receipts and labels coverage as partial; its empty array is not proof of no historical bids. Undeployed treasury responses contain zero earned revenue. `/analytics/curation` reads the current permitted owner choice from the contract.

The traits route returns frozen artwork attributes and their source/document hashes. Minted editions additionally verify root-level NFT metadata before reporting `published`; conflicting traits return 409. Unminted replay traits do not imply NFT ownership. See [NFT traits](NFT_TRAITS.md) for the metadata schema and legacy behavior.

Artwork and epoch lists accept `limit` (1–100) and nonnegative `offset`. Epoch detail omits the full record array and links the immutable snapshot. Production rerender verification requires administrator authorization; public integrity checks remain bounded. The public frontend proxy excludes administrator/demo paths. `/health` reports worker-managed integrations in production and does not imply credentialed acceptance.

Hash verification also has a process-wide concurrency bound (default one) to control dataset memory use; a busy verifier returns 429 with `Retry-After`. Production blob requests redirect to CloudFront instead of buffering whole snapshots through the API. Size the worker/API and reconciliation window against actual authenticated dataset volume before commissioning.
