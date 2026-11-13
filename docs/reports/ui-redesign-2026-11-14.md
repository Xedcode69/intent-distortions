# Gallery interface update — 14 November 2026

The interface now uses a light gallery layout, larger artwork, a restrained lime accent and original typography and composition. The home page, collection, Drops, historical story, marketplace, artwork traits and collection economy share the same visual system. The artwork displayed is the project's recorded artwork; no fictional listings or prices were added.

Long explanations, proofs, schedules, simulators and wallet maintenance tools use disclosures. Trading terms and the consequences of early withdrawal remain available alongside the relevant actions. The historical presentation still plays its statistics chapters before revealing the artwork, with static, animated and layer views afterward.

No third-party template code, template images, screenshots or downloaded site sources are part of this change. Space Grotesk is served locally with its SIL Open Font License. The existing wallet-selector stylesheet retains its upstream Inter font import.

## Validation

| Check | Result |
| --- | --- |
| Frontend production build | Next.js compilation, TypeScript, page generation and standalone output passed. |
| Existing JavaScript regression tests | 13 passed, covering commitments, family selection, trait integrity, economy arithmetic, marketplace fees, proxy boundaries and signer scope. |
| HTTP smoke checks | Home, Drops, collection, market, historical demo, economy and historical artwork returned 200. The legacy `/genesis` route still redirects to `/drops` with 308. |
| Historical replay | 130,086 successful eligible records and 37 recognized source networks remain recorded. API verification passed, including frozen asset mapping, family selection and visual features. |
| Published assets | Image, scene and trait document SHA-256 values match their published commitments. The canonical historical PNG remains `8fec6c77137badb4cd124b8235287eb36ab902ebbb0f27e6b78829dd47af8fca`. |
| Preview marketplace | Undeployed state, empty listings/offers/royalties, 500 basis point fee and disabled cross-chain funding remain correct. No financial action was submitted. |
| Font | Local WOFF2 signature, 22,288-byte response and license checked. |
| Desktop visual review | Home, Drops and historical story inspected in native Chrome against the local preview. The real artwork loaded on the home page and the historical story displayed its activity chapter. |
| Responsive and accessibility work | Breakpoints at 1,150, 850 and 580 pixels, mobile navigation, skip link, focus indicators, disclosure controls and reduced-motion styles implemented. Physical mobile, screen-reader and complete keyboard journeys remain unverified. |
| Publication scan | No configured credential values found in publishable project files. Private research references and local QA tools remain ignored. |

This update changes the frontend only. It does not establish live deployment, contract commissioning, financial transaction acceptance or an independent security audit. Backend and contract suites were not rerun for these presentation changes; their existing acceptance requirements remain in force.
