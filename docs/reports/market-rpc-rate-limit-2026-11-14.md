# Marketplace wallet RPC rate limit — 14 November 2026

The reported Meteor purchase confirmation returned JSON-RPC code `-429`,
"Rate limits exceeded." A read-only chain check found ECHO-000004 still owned
by `iddeployertest.testnet`, its 1.6 NEAR listing active with no pending sale,
and buyer `idtester1.testnet` already holding 0.01 NEAR available market storage
with zero market credit. No successful purchase was visible. Without the
wallet's transaction hash this does not prove every native-balance movement;
no payment was automatically resubmitted to test the fix.

The current official Meteor executor uses `https://test.rpc.fastnear.com` for
testnet and does not consume the connector's custom provider list for its
Meteor signing path. Changing the app's backend RPC URL therefore does not
change the popup's provider. Its code was inspected only as an ignored local
reference; no vendor executor was modified, copied into source or committed.

Changes shared by production and testnet:

- Pause background query polling and wallet-session refresh while an artwork
  action prepares/reviews/signs, including overlapping/nested approvals.
  Explicit ownership, price, rights and clock validation remains fresh.
- Poll marketplace, ownership and shared financial views every 30 seconds,
  instead of 15; disable focus-triggered refetch storms when wallet windows
  return focus. Remove duplicate post-action refetch requests.
- Read market storage before the final validation. Revalidate again after a
  setup transaction, but avoid repeating the same reads when no setup occurred.
  Reuse the freshly verified health/clock response to construct expiry values,
  instead of making another eight-read lab health request before signing.
- Show a clean rate-limit message with explicit ownership/credit checks and
  no automatic payment retry. A rate-limit failure does not immediately trigger
  another global refetch burst. Meteor's own popup remains wallet-controlled.
- Back off bounded read-only JSON-RPC `-429`/`429` errors even when the provider
  returns HTTP 200. Keep messages redacted, preserve missing-block semantics,
  and do not automatically rebroadcast JSON-rate-limited payment submissions.

Validation: 198 backend tests passed, one PostgreSQL integration skipped;
34 JavaScript tests passed; Next.js production build/TypeScript passed. Tests
cover nested approval pausing/release, failure cleanup without repeated payment,
error redaction, bounded JSON rate-limit backoff and unchanged missing-block
handling. Existing cancellation, wallet-change and rights-change checks pass.
The testnet server is restarted at http://127.0.0.1:3004. Production/testnet
release archives are rebuilt from the same source with separate WASM sets.

The site cannot remove an external wallet's public-provider quota. Close the
failed popup and extra app tabs, allow the rate window to recover, then refresh
ownership/listing/credit before approving the intended purchase again. Persistent
Meteor-provider errors require wallet/provider support or another supported
wallet; the app does not replace the user's wallet or sign with operator keys.
Real wallet purchase acceptance remains for the user to perform. No new
financial transaction or contract deployment was performed in this fix.
