# Public data and privacy

Use only the documented authenticated Explorer endpoint. No private-shard access or decryption is attempted. Optional intent and chain hashes need not exist. Masking/non-swap records without required swap fields are rejected rather than being counted as completed swaps.

Raw captured API pages may contain public addresses and memos. They remain inside ignored `data/captures/*.raw.json`; do not publish those files. Public snapshots contain only schema version, created-at seconds, asset identifiers, hashed record identity, and decimal-string public USD fields. Identity hashes are linkable pseudonyms and may be vulnerable to guessing; do not describe them as anonymization.

AI prompts contain aggregate statistics, chain/route labels and seed only. No wallet addresses, deposit memos, raw account records, or secret values are sent. The worker stores the exact validated creative response and request metadata. No unpublished monetary values are inferred. Public shield events are not used as substitute swap counts.

Do not upload a raw capture when pinning artwork/provenance. Only the exported redacted bundle is intended for publication.
