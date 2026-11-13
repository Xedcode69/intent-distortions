# NFT traits validation — 2026-11-13

This release adds `echo-nft-traits-v1` to the frozen artwork publication, NFT mint metadata and artwork/demo views. The traits are derived from committed scene/provenance bytes; the original PNG, scene, seed and provenance are unchanged. Contract-generated calendar traits follow the enforced edition schedule. Balances, ownership and draw eligibility remain live contract data.

Validation completed:

- Python: 116 passed, 1 skipped. The optional PostgreSQL integration test was skipped because its dedicated URL was not configured; SQLite and all trait tests passed. An existing Starlette deprecation warning remains.
- Rust: 47 passed (18 auction, 25 NFT, 4 vault), including root-level trait preservation, authoritative calendar/wallet fields and unchanged metadata after transfer.
- JavaScript: 12 passed, including modified trait-byte/attribute rejection and the existing browser-compatible family-selection, proxy, signing and accounting checks.
- Next.js production build and TypeScript checks passed.
- Local HTTP checks passed for the demo, gallery, trait API and frontend proxy; all three public asset hashes matched. The actual published trait document also passed the browser-compatible WebCrypto verifier (31 core attributes).
- Epoch verification passed. Historical publisher rerendered/verified the real-data replay and allowlisted only PNG, scene and aggregate trait JSON for the new public edition.
- NEAR 2.14 sandbox: the unmodified production WASM passed the full lifecycle with 33 supplied artwork attributes plus three contract-generated calendar attributes. Seven dedicated keyless accounts, creator delivery, auctions, automatic refunds, secondary transfers, failed transfer recovery, early withdrawal, rollover, BLS-verified draw and failed prize retry passed. No test-only contract setter was added. As in the prior economy report, sandbox state intervention selects the captured historical beacon round because the future scheduled proof does not yet exist.

The saved demo still represents 130,086 successful captured records, 37 recognized source networks and the Crystalline/glass/celestial artwork. Public trait JSON SHA-256:

```text
a9b51cf55b7927642730ccfdf2fa07ed6792b8d413f5b80651d9a93237ce666d
```

The original image remains:

```text
8fec6c77137badb4cd124b8235287eb36ab902ebbb0f27e6b78829dd47af8fca
```

Current locally built WASM SHA-256 values:

| Contract | SHA-256 |
| --- | --- |
| NFT | `f7ff7cecfaa77e9fb1b0f6c990bd85a5a0ea9d0c66796c88c48169e85afebc53` |
| Auction | `3198e091c247facb14e4767def8313f4c1e64e7ae0f40f2f39e88b8d8ef76e9f` |
| Vault | `0bd2832599944647bcf6d019600409d1e709efe9eb4a1e24d0641c943af9b2f1` |

The NFT hash supersedes the NFT artifact in the earlier economy validation report. Review and pin the new hash before deployment; preflight now requires the contract's trait capability. No real-network mint, deployment, bid or transfer was performed. Existing immutable NFTs are not retroactively changed. Marketplace display of custom NEP-177 `extra.attributes` still requires compatibility testing. HTTP and WebCrypto checks do not substitute for browser visual QA or independent contract review.
