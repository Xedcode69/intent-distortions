# Renderer 4: measured controls and verifiable family selection

New mapped editions use `echo-renderer-4`; frozen renderer-1/2/3 editions keep their original algorithms. A new live protocol commitment is required before deployment. The historical demonstration reuses its verified capture and network lookup in a fresh isolated directory, without downloading transaction pages again.

## Family draw

The fixed ordered list is orbital network, fractal branches, crystalline, flow field, spiral constellation, particle nebula. Indices are zero-based. For the frozen 32-byte art seed and a counter starting at zero:

`digest = HMAC_SHA256(seed, ASCII("NEAR_ECHOES_FAMILY_V1") || u64_be(counter))`

Let `limit = 2^256 - (2^256 mod 6)`. Reject a digest integer at or above the limit and advance the counter; otherwise select `integer mod 6`. This avoids modulo bias under the pseudorandom-seed assumption. Weekly repeats are allowed. Policy `seed-rejection-six-v1`, digest, index, first accepted counter and family are recorded. The Demo independently recomputes the draw with WebCrypto and refuses missing or mismatched proofs for renderer-4 publications.

AI receives a schema with composition fixed to that family. It chooses styling, title and description; a response changing the composition is invalid. Owner curation changes material/theme while preserving the selected family. Legacy curation behavior is retained for older versions. The first valid response is persisted; retries retain the same seed, family and frozen inputs. Palette syntax is explicitly six-digit RGB hex and is validated. Safe failures disclose only phase, exception type and optional HTTP status, never provider messages or credentials.

## Frozen measurements

`echo-visual-features-v1` derives these measurements from the complete canonical snapshot and frozen network lookup:

- Directed route counts, first/last creation-time positions and logarithmic weights.
- Incoming/outgoing counts, normalized flow imbalance and hub importance.
- Weighted reciprocal cross-network activity, cross-network share and route diversity.
- Deterministic greedy weighted-modularity communities on the 64 busiest networks; remaining networks keep separate groups. Unmapped nodes cannot supply inferred community links.
- Activity in 48 equal intervals, coefficient-of-variation burstiness mapped to `[0,1]`, quiet intervals and periodic peak count.
- Exact asset-ID diversity, trade-size Gini coefficient, top-one-percent reported input USD share and median/p90 input USD values, with explicit coverage.

The full vector is saved as `visual-features.json` and referenced in provenance. AI context retains all scalars plus the 16 busiest hubs/routes; rendering retains the full graph. Public presentation exports aggregate measurements without per-record identities. Creation time is not settlement/completion time.

## Implemented family controls

| Family | Controls | Main drivers |
|---|---|---|
| Orbital | Eccentricity, tilt, 2–6 nested rings, hub-weighted layout, rotation direction | Flow imbalance, hubs, reciprocity |
| Branches | Depth 3–7, branching ratio 2/3, taper, cubic curvature, leaf density, trunks | Complexity, route diversity, bursts, hub concentration, asset diversity |
| Crystalline | Facets, irregularity, growth direction, 2–6 subdivisions, translucency | Symmetry, complexity, asset diversity, bursts, flow imbalance, reciprocity |
| Flow field | 1–8 interacting vortices, turbulence, thickness, integration steps and stream budget | Communities, bursts, size inequality, cross-network share, complexity |
| Spiral | 2–8 arms, winding, asymmetry, 3–12 temporal bands, pitch | Activity peaks, bursts, flow imbalance, asset diversity, complexity |
| Nebula | Cluster count, density, elongation, overlap, diffusion, dust | Communities, hubs, size inequality, reciprocity, complexity |

All families include full aggregated routes, a bounded temporal particle sample, a previous-image-hash orbit and edition/seed border signature. All records contribute to the dataset commitment even when the visible sample is bounded. Values are saved in the scene and shown in the Demo controls panel.

## Primitives, material and light

The scene supports dots, polylines, cubic Bezier curves and filled/stroked polygons. Ribbons are polygons around sampled paths. Coordinates are bounded, and depth changes perspective projection, shading and stable draw order. Lighting is a stylized 2D treatment rather than a physical ray tracer.

Material profiles have concrete drawing behavior: **glass** uses translucent faces and lit edges; **ink** uses hatching and can choose paper backgrounds; **grain** adds stippling and stronger seeded grain; **iridescent** shifts surface hue with light/depth; **luminous** adds bloom and lighter translucent fills. Keyword-compatible descriptions resolve deterministically. Theme selects celestial, tidal, botanical, ember or electric background treatments. Complexity changes actual geometry and texture budgets. Network identity determines a stable base hue, harmonized with the AI palette; adding a network does not shift existing colors by list position.

The canonical output remains a 1440×1440 PNG, with SVG geometry and WebP thumbnail. SVG/browser glow can differ from raster glow. Tests cover all six families, five material profiles, bounded controls and repeatable raster output.

## Animated presentation

Static, Animated and Layers views use the recorded scene. Surfaces, textures and lighting have separate layer controls in both the Demo and gallery DNA viewer.

The 48-bin activity profile controls light amplitude, burstiness controls pulse tempo, and route frequency controls light count and travel rate. Highlights are capped at 80 busy routes while all routes remain in the scene. Orbital motion follows the saved rotation direction. A 24-second reveal uses creation-time positions for transaction marks and route appearances; structural growth is an artistic encoding. The activity profile repeats over 32 seconds. These effects do not measure settlement speed.

Play/Pause, Restart and Show full scene / Reveal the week controls are provided. Reduced motion starts paused with the full scene visible. Offscreen/hidden animations stop painting, and cached surfaces avoid redrawing every primitive each frame. Browser checks verify file hashes and independently recompute the family draw. Full dataset/scene/PNG replay remains an offline or authorized server operation.
