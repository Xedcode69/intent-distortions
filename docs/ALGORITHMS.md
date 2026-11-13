# Protocol algorithms v1

All protocol times are UTC. The production window is Sunday `[00:00,17:00)`, with the first default-network drand round released at or after 18:00 fixed in advance. Reconciliation default is 3600 seconds; automatic production sealing is not enabled in this prototype. Consecutive activity intervals are `[previous checkpoint,current checkpoint)`, comparing documented created-at seconds promoted to integer nanoseconds against precise block checkpoints. This is creation time, not settlement time.

## Encoding

* Epochs and PRNG indices are unsigned 64-bit big-endian integers.
* Hashes/randomness are raw 32-byte digests. NEAR block hashes are base58-decoded to 32 bytes.
* Domain labels are exact ASCII bytes, with no implicit NUL terminator.
* Records use RFC 8785 serialization via `rfc8785`. Amounts remain validated decimal strings or null, never binary floats. Decimal spellings are preserved after decimal fixed-point normalization; `2.00` and `2` are distinct schema values.
* Record identity is `SHA256("ECHO_ID_V1" || JCS([depositAddress, depositMemo]))`. It is pseudonymous, not anonymous. Shared optional intent/chain hashes never cause a merge. Missing or conflicting deposit identity blocks reconciliation.
* Sort by `(created_at_unix, public_record_identifier)`.

## Hashes

`record_hash = SHA256("ECHO_RECORD_V1" || JCS(record))`.

`leaf = SHA256(0x00 || record_hash)`; `parent = SHA256(0x01 || left || right)`. Duplicate the last node for an odd row. The empty tree root is `SHA256("ECHO_EMPTY_V1")`. Snapshot hash is SHA-256 of the entire ordered JCS array.

## Randomness

Pin drand default chain `8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce`, public key in `randomness.py`, period 30, genesis time 1595431050, scheme `pedersen-bls-chained`.

Verify the BLS signature over `SHA256(previous_signature || u64(round))` with the pinned key and `py_ecc.bls.G2Basic` (the drand G2 NUL DST). Then require `SHA256(signature) == randomness`. Reject any unexpected round/network. The previous signature is an input authenticated by the current beacon signature; the entire prior chain is not replayed. This assumes the honest threshold beacon network.

`selection_seed = SHA256("NEAR_ECHOES_BLOCK_SELECTION_V1" || u64(epoch) || randomness)`.

Let `D=61200`, `limit=2^256-(2^256 mod D)`. Accept the seed integer if below the limit; otherwise repeatedly hash `"NEAR_ECHOES_REJECT_V1" || selection_seed || u64(counter)`, starting counter at one. Return `Sunday_start + integer mod D`.

Query the first finalized historical NEAR mainnet block with `timestamp_nanosec >= selected_seconds*10^9`. Check its actual predecessor timestamp is strictly less and its height does not exceed the finalized tip. Missing historical access never substitutes the latest block.

## Artwork

`seed = SHA256("NEAR_ECHOES_ART_V1" || u64(epoch) || merkle_root || block_hash_bytes || randomness || previous_image_hash)`.

Genesis image hash is `SHA256("NEAR_ECHOES_GENESIS_V1")`.

Each visual random value uses `HMAC_SHA256(seed, ASCII(label) || ":" || u64(index))`; convert the first eight bytes as big-endian uint64 divided by `2^64`. Independent labels include layout, geometry, particles, noise and signature. No unseeded RNG enters the scene.

Normalized chain entropy controls deformation. Created-at position within the interval sets angle. Radius uses square-root normalized seed values. Log public USD volume controls particle size, light, and mark prominence; missing volume is explicitly neutral, not invented. Source chains choose palette positions. Every record drives a route; every record also affects the complete dataset root and seed. Particles are capped at `min(2400,floor(100*sqrt(n)))`.

Six bounded families transform trajectories: orbital, branches, crystalline, flow field, spiral and nebula. The scene includes a hash-derived previous-edition orbit and a visible constellation encoding the 64-bit edition and first 128 seed bits. This ensures distinct edition signatures, not guaranteed perceptual dissimilarity.

The saved direction influences composition, palette, symmetry and description. It cannot change membership, seed or auction rules. PNG and SVG share scene primitives; raster glow is additional deterministic presentation. Byte-identical replay requires the same Pillow and renderer versions. The image's immutable content hash is authoritative across environments.
# Renderer-v2 deployment note

New live protocols pin `echo-renderer-2`. It aggregates route pairs and evenly samples the complete ordered interval, capping particles at 2,400. The six families now use distinct constructions: orbital arcs, recursive branching, crystalline triangular meshes, integrated flow fields, radius-twisted spirals, and seeded Gaussian nebula clusters. Separate HMAC substreams drive each system. Geometry stays bounded at weekly dataset scale. The original renderer-v1 frozen scene remains replayable and its canonical image was not replaced.

`merkle-proofs.json` for new editions uses the compact `echo-merkle-index-v1` tree-level format. It stores O(n) tree nodes; a selected membership proof is recovered in O(log n) without rebuilding the entire tree for each record. Older exports containing individual proof arrays retain their original hashes.
