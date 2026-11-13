# Demonstration

## Local, no credentials

Run `uv sync --locked`, install frontend dependencies as described in the README, then use `uv run --locked python scripts/dev.py`. The boot path renders one fixed synthetic edition and then serves it idempotently. The gallery and metadata always identify the fixture. The auction and treasury contain no simulated financial state.

Suggested presentation:

* Studio → open the latest artwork.
* Reveal its DNA → toggle routes, particles, inherited orbit and signature.
* Provenance → verify all commitments.
* Live genesis → replay the demo; observe the image hash remains fixed.
* Auction → show that real custody and signing are prerequisites.

`uv run --locked python scripts/export_artwork.py` writes the portable frozen bundle under `data/exports/demo-000001/`. `uv run --locked python scripts/verify_epoch.py` checks byte hashes and exact PNG replay. A local freeze cannot be changed by an HTTP reset. Separate experiments need a new disposable database; never reset a production edition or reuse its onchain epoch namespace.

## Public randomness evidence

`fixtures/sample-epoch/verified-beacon.json` is a captured real default-network drand beacon for the fixed 2026-11-08 Sunday 18:00 UTC release. Round **6624326**, selected timestamp for epoch 1 **1794097030**. The test verifies its BLS signature offline and rejects altered randomness. Run `scripts/capture_beacon.py` to independently fetch the beacon and historical selected block. The public archival provider may rate-limit; configure an alternative archival URL when necessary. An unsuccessful block lookup is not a verified selection and never falls back to latest.

This separate real beacon does not change the already-frozen synthetic artwork's evidence. Its beacon, block and records remain explicitly synthetic.

## Real historical swap capture

Set `NEAR_INTENTS_PARTNER_JWT`; capture a full eligible interval using `scripts/fetch_sample_swaps.py --start <seconds> --end <seconds>`. The full query completes before a capture is considered usable. Raw pages remain ignored/private; redacted canonical bytes and source query metadata are retained for audit. Replay with `EXECUTION_MODE=historical_replay` and `scripts/run_replay_epoch.py` after obtaining valid archival evidence.

Set the NEAR AI key/model before generating a **new** replay edition. An existing frozen demo will retain its recorded fallback instead of silently changing its direction. A persisted creative generation result is replayed, not re-requested to select a more attractive result.

## Real testnet mint and auction

Prerequisites: deployed initialized **dedicated demo** contracts, operator/minter plus two funded bidder accounts in the official CLI keychain, and public immutable image/provenance URLs containing the exact exported bytes. Configure contract names in `.env`. The supplied runner refuses mainnet and checks public URI hashes and existing onchain commitments before minting.

```text
uv run --locked python scripts/testnet_lifecycle.py --minter operator.testnet --bidder-a alice.testnet --bidder-b bob.testnet --media-uri ipfs://<image-cid> --provenance-uri ipfs://<provenance-cid> --wait-for-end
```

The runner performs real CLI-signed testnet calls, confirms NFT/auction state, registers bidders, submits two bids when the auction has no existing bid, waits for the effective end, settles, verifies winner ownership, and claims the first bidder's losing escrow. It prints actual CLI receipts and RPC results. It never generates a fabricated receipt hash or automatically retries an uncertain signed call. If interrupted after a bid, inspect onchain state; it preserves existing bids on restart instead of blindly submitting them again.

Use the default 1 and 1.1 NEAR bids with the current `new_economy` initializers in [ECONOMY.md](ECONOMY.md). Economy contracts enforce the actual 24-hour deadline; `--wait-for-end` really waits. They also create/fund the dedicated wallet, and the three November launch editions take the creator-mint path without bidding. Legacy compressed laboratory contracts remain a separate test mode. Public content upload, account creation and deployment are prerequisites, not simulated by the runner.

The historical site includes a separately labelled financial simulator, and the standalone explainer's auction step uses the same 20/80 allocation and early-exit rules. Neither simulates onchain balances in the production API or claims that the saved artwork was auctioned.

No real mint, bids or settlement have been executed yet because credentials are absent. Those steps, real swap provenance and a live AI response remain necessary before claiming the brief's full acceptance criteria or recording a hackathon proof video.
