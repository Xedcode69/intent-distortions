# Drops page validation — 2026-11-14

Renamed the Live Genesis destination to `/drops`; `/genesis` now redirects permanently with HTTP 308. Navigation and studio links use Drops. The page presents the upcoming edition's schedule and creator-mint/24-hour auction policy, edition-specific creation progress, the finished static/animated artwork and a paginated archive with source counts and separate NFT/auction statuses.

The new read-only `/api/v1/drops` feed follows the next uncreated live edition rather than an older active auction. It distinguishes the beacon time from the freeze/earliest creation time and preserves overdue editions instead of silently skipping them. Preview and replay artworks stay labelled and do not advance production numbering. Opening the page creates no release, generation job, AI request or chain transaction.

The worker persists per-pass received rows/pages and completed unique/successful counts, resetting counters between reconciliation passes. Generation updates only advisory job phases; frozen inputs, artwork bytes, seed and provenance remain unchanged. Unknown collection totals remain null; progress bars stay indeterminate until the pass completes. The UI refreshes every five seconds and displays delays/stale state without fabricating a rendering percentage.

Validation completed:

- **132 Python tests passed; 1 optional PostgreSQL test skipped.** New coverage checks first-drop timing, no read-side generation, old auctions versus new creation, automatic artwork appearance, per-pass counters, successful-only contributions, delayed/stale stages, overdue schedules, replay separation, archive pagination and live worker callback wiring. The existing Starlette deprecation warning remains.
- Next.js production build and TypeScript checks passed, including `/drops` and the legacy redirect.
- Root epoch/provenance rerender verification and Render deployment-definition validation passed.
- Local HTTP checks passed for `/drops`, its API feed and the 308 redirect. The saved replay still reports 130,086 contributing records and 37 source networks with its original image hash. The upcoming production preview is ECHO-000001: November 15, 2026, beacon at 18:00 UTC, freeze/earliest creation at 19:00 UTC with the configured one-hour reconciliation delay. Completion is not promised at the freeze timestamp.

No new live artwork generation, paid AI request or real-chain transaction was initiated. Contract code was unchanged. Browser visual/wallet QA was not performed; local validation used HTTP, application tests and the production build.
