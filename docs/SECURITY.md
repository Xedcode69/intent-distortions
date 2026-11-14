# Testnet trust and security boundaries

This build handles test NEAR only. Settings and the signer reject mainnet execution. The source RPC intentionally reads mainnet blocks and the Explorer reads public mainnet swaps. No confidential-shard access is attempted. Cross-chain 1Click funding is disabled for this testnet product.

Fresh weekly contracts are created/deployed/initialized atomically without access keys. Code hashes and keylessness are verified before use; no upgrade or artwork replacement method exists. The old financial rehearsal contracts and their balances are preserved. Genesis remains sealed in its original pinned contract. This storage layout is for fresh accounts, not an in-place upgrade.

The minter can initiate a new scheduled edition but cannot replace a prepared/sealed one. The artwork freeze binds geometry, metadata, source commitments, accepted direction and both SVG hashes. The worker validates source provenance before publication. AI styling is not proof of provider completeness; minter/source correctness remains a trust assumption. No AI decides payouts, financial rules or raffle winners.

Dedicated edition accounts have no access keys and accept constrained calls from the NFT contract. Current NFT ownership, transfer locks, fixed beneficiaries for already-authorized payments, stale financial-snapshot rejection and debit-before-transfer accounting protect transfer/payout races. Failed native transfers restore retryable credits. Neither seller nor buyer receives an edition-account private key or arbitrary arbitrary-code authority.

Secrets remain on the backend or in the local NEAR CLI OS keychain. Vercel receives only BACKEND_URL and the public testnet profile. Hosted signing uses a mounted operator key file and receiver/method/deposit/gas limits. Exact signed bytes are journaled before broadcast; ambiguous outcomes stop new signing. Fresh deployment actions are inspected against a reviewed plan before broadcast.

Public chain-media reads pin code and finalized block, require keylessness/sealing and verify SHA-256. SVGs are served with sandbox/content-type protections and displayed as images. Request bodies, verification concurrency and public receipt ingestion are bounded. The frontend proxy blocks administrator/demo routes. Private source snapshots are not served by the live content endpoint. Admin APIs require a private bearer token.

PostgreSQL and the private archive require backups and tested recovery. One leased worker must remain running for timely observation, auctions and payouts; /readyz detects a stopped combined worker, not every upstream outage. Alert on delayed releases, unknown effects and failed transfers. A missed freeze cannot be silently reconstructed later. Independent security review, fresh weekly end-to-end acceptance and managed-host recovery drills are still outstanding; this is not a mainnet-ready assertion.
