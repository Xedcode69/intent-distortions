# Verified historical demo — 8 November 2026

Artwork: **Interchain Flux**. Creative direction: NEAR AI Cloud (`Qwen/Qwen3-VL-30B-A3B-Instruct`).

**130,086 unique successful records**, collected in **131 cursor pages**. The completed capture matches the independent smaller-window count.

- Interval: 1 November 2026 00:00:00 UTC to 8 November 2026 00:17:10.218994184 UTC, end exclusive.
- Calendar-week count: 129,940. Additional checkpoint interval: 146 records over 17 minutes, 10.218994184 seconds.
- Capture completed: 2026-11-13T11:15:28+00:00. SUCCESS statuses are observed at capture time.
- Test records are excluded by omitting the cursor endpoint's presence-based `showTestTxs` flag.
- Every returned status is checked; time boundaries and deposit identities are validated before the dataset is committed.
- The initial all-status in-memory collection was discarded. The intermediate test-inclusive result is retained privately for diagnosis and is not the public demo.

Acceptance checks passed: full scene and PNG reconstruction; seed, snapshot and Merkle commitments; sample membership proofs; identical repeat run; rejection of altered records and commitments. No NFT mint or auction was run.

[Canonical artwork](../../frontend/public/historical-demo/editions/b8c7ca7e88cb5f74d3f0aaec3bc87e9d659eaf264602ed2282cf716274473d4a/artwork.png) · [Public presentation index](../../frontend/public/historical-demo/index.json) · [Advance count audit](2026-11-01-success-count.md)

Image SHA-256: `f03c8030caa16e6b3198b502d5d77cddac4b7ddcbbd109ec659b33950755237a`

Dataset Merkle root: `c1f7fec0e194e8bf23b63b7827fe0a58d25b5b1472949d841f3f897985960585`

The public bundle contains only the canonical PNG, recorded scene, aggregate statistics and verification commitments. Raw captures, per-record snapshots, databases and credentials remain private. These checks establish integrity and reproducibility, not a cryptographic proof of provider completeness or original as-of-freeze statuses.
