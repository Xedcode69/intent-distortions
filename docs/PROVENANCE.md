# Provenance and verification

The source pipeline preserves exact interval bounds, SUCCESS-only membership, pseudonymous ordered record identities, a Merkle root, the verified mainnet block, verified drand beacon, previous canonical onchain SVG hash, registry mapping, seed-selected family, NEAR AI first-valid direction, visual features and scene/file hashes. Complete source observations must agree before the fixed freeze. Merkle membership proves inclusion, not provider completeness or historical status truth.

Source PNG/scene hashes remain immutable internal evidence. They are distinct from the final canonical onchain SVG hashes; no old source file is relabelled as the new NFT. After publication, public artwork responses resolve static/animated views from the sealed recipe and return their frozen hashes. Each later weekly seed continues from the preceding sealed static SVG hash; the first continues from preserved genesis.

Public inline onchain provenance contains source commitments, seed, Merkle root, direction/model, motion controls and traits. The complete raw dataset and provider response pages are not stored in the art contract or served by live content routes. Geometry and renderer are onchain and recover both views without a media host. Browser rasterization can differ; the SVG bytes and recipe hashes are authoritative.

`uv run --locked python scripts/run_demo_epoch.py` creates an isolated synthetic regression fixture under data/verification; `uv run --locked python scripts/verify_epoch.py` checks it, including scene/statistics reconstruction and exact PNG replay. Passing these checks is not a live source capture or fresh weekly mint. A saved live source edition can be verified by its explicit ID using the configured private archive. The site separately checks onchain code, keylessness, sealing and media hashes.

NEP-177 media_hash and reference_hash encode raw SHA-256 bytes as base64. Public weekly metadata carries an inline reference and compact near:// media identifier; individual nft_token views embed the static SVG. See ONCHAIN_ART.md for the staged freeze protocol.
