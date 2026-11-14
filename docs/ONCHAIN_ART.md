# Immutable onchain art study

`intent-distortions-onchain-v1` is a separate prototype NFT format. It derives
one study from the saved historical genesis, retaining its accepted NEAR AI
direction and transaction-derived geometry. It does not change the original
edition, enter an auction or create reward rights. The production weekly worker
continues to publish the existing format; switching its NFT/auction bindings is
a separate rollout.

## What is preserved

The contract stores a packed vector display list, the complete accepted artistic
direction, traits, frozen motion controls and source commitments. Its deployed
WASM contains the complete SVG renderer. Neither view needs Python, Pillow,
IPFS, a hosted image, a JavaScript library, an external font or another AI call.
The site is a convenience reader; anyone can recover the bytes using NEAR RPC.

The historical run already obtained its direction from NEAR AI Cloud. Preparing
this prototype verifies and reuses that response; it does not request a new
direction or claim a new week's transaction capture. The six-family seed policy
is preserved. Source completeness and raw-record availability remain separate
from artwork availability: the raw dataset is committed, not copied into this
art contract.

This format deliberately retains resolved geometry for precise recovery. It is
not a complete port of all Python scene-generation algorithms into Rust. Points,
radii and strokes use integer thousandths; RGB and opacity are packed directly.
The new SVG bytes are authoritative for the new study. They are not identical
to the original PNG or original SVG. Screen pixels can differ between browsers.

## Finality

`begin_edition` permanently binds the token ID, source provenance, recipe hash,
metadata and initial recipient. Storage is prepaid. `append_recipe` only appends
bounded chunks at the exact next offset. There is no reset or overwrite method.
`seal_and_mint` validates the complete recipe and both SVG budgets, records their
hashes, seals the record and mints its one NFT atomically. Excess storage deposit
is refunded to the operator. A failed seal leaves the committed draft intact;
it never substitutes another AI response or different geometry.

Duplicate token IDs, recipe hashes and source provenance commitments are
rejected within this collection. The NFT can transfer using NEP-171; its artwork
and traits remain fixed. Public art can still be copied outside this collection.
The reused artistic traits describe the source scene generator. The onchain
format and SVG renderer are identified separately in NFT `extra` and `get_config`.

The prototype account is created atomically with CreateAccount, Transfer,
DeployContract and initialization, **without AddKey**. Its code exposes no
upgrade, deletion, metadata replacement, key-management or arbitrary execution
method. The build checks an export allowlist. The reader verifies direct code
hash, testnet identity, sealed hashes and the absence of account keys. A parent
account does not gain an upgrade key for its keyless child.

Permanent locking is irreversible. This is a testnet prototype, not an audited
mainnet deployment. Future rendering versions need a new immutable deployment;
they cannot revise published studies.

## Frozen motion and variety

Both views use the same stored shapes. The static view shows the complete
composition. Native SVG animation changes its presentation through fixed rules:

| Family | Motion available in this format |
|---|---|
| Orbital network | Gentle orbital drift, activity breathing, moving route highlights |
| Fractal branches | Branch-path reveal, depth-derived phase, particle pulses |
| Crystalline | Phased facet shimmer, activity-controlled intensity |
| Flow field | Fixed current-path highlights and restrained drift |
| Spiral constellation | Gentle rotation, temporal particle phases |
| Particle nebula | Centered breathing, particle and activity pulses |

The accepted seed and measured burstiness, route diversity and reciprocity select
a bounded variant. Burstiness and trade-size inequality set motion strength;
flow imbalance controls a published artistic direction rule. Each route's frozen
frequency weight adjusts its highlight period. Network communities already
influence the stored geometry. These are artistic encodings, not measurements
of settlement speed or geographic movement.

The activity profile has a 32-second cycle; facets and routes have their own
fixed periods. Pause/replay in a viewer does not modify the edition. No future
transactions, owner identity, financial state or current AI response enters the
renderer.

The full-detail study's successful seal consumed approximately **297.6 Tgas**
across its execution receipts, close to NEAR's 300 Tgas transaction limit. A
200 Tgas attempt reverted without minting. This prototype proves finality and
chain-only recovery for this scene; larger weekly editions need renderer
optimization or staged view validation in a **new** contract version before
production rollout. Byte/shape limits alone are not a guarantee that every
permitted scene can seal within the gas limit. Published study code stays fixed.

## Prepare and build

Run Python commands from the repository root using the locked uv environment.
Keep the existing testnet workspace; do not overwrite its source edition.

```powershell
uv run --locked python scripts/prepare_onchain_art.py data/testnet-rehearsals/full-lab --output data/onchain-prototypes/genesis-idart1
uv run --locked python scripts/build_onchain_art.py --test --optimizer-js .tools/binaryen-version_125/wasm-opt.js
cargo +1.95.0 run --locked --manifest-path contracts/Cargo.toml --target-dir contracts/target/testnet-lab -p intent-onchain-art --example render_recipe -- data/onchain-prototypes/genesis-idart1/recipe.bin "Echo of the Hub" data/onchain-prototypes/genesis-idart1
```

The optional optimizer is the official Binaryen 125 Node release. Its archive
`binaryen-version_125-node.tar.gz` has SHA-256
`07c13f3f0c805ba44a86c631f5bcc2fbe8873ce294d029f9568ef8b177c0dc32`.
The build requires its exact version and validates WASM exports. Tool binaries
stay ignored. Windows native tests need the installed Visual C++ environment
and the existing `AWS_LC_SYS_PREBUILT_NASM=1` configuration. Set `SSL_CERT_FILE`
to a trusted CA bundle if your network requires one; never disable TLS checking.

Preparation performs a full source replay and allowlists public artistic fields.
Prepared recipe/metadata files cannot be overwritten with different bytes.
They remain under ignored `data/`; raw captures, credentials and operator
journals must not be published or committed.

## Review, deploy and recover

```powershell
uv run --locked python scripts/onchain_art_testnet.py plan data/testnet-rehearsals/full-lab data/onchain-prototypes/genesis-idart1
# Review the account, recipient, WASM/recipe/view hashes, funding and SHA-256.
uv run --locked python scripts/onchain_art_testnet.py send data/testnet-rehearsals/full-lab data/onchain-prototypes/genesis-idart1 --send --plan-sha256 REVIEWED_PLAN_SHA256
uv run --locked python scripts/onchain_art_testnet.py verify data/testnet-rehearsals/full-lab data/onchain-prototypes/genesis-idart1 --plan-sha256 REVIEWED_PLAN_SHA256
```

The default account is `art-v1.<operator>`. The prepared team's wallet receives
`ONCHAIN-PROTOTYPE-000001`. No account key is created or removed. The operator
must cover the shared code, recipe/storage prepayment and a conservative gas
reserve. Storage prepayment and reserved transaction gas are not all consumed
fees. Measure the final storage delta and refunds rather than treating the
upfront transfer as the artwork's price.

Recipe calls are signed through the official CLI in **display-only** mode.
A strict decoder checks signer, receiver, method, arguments, gas and deposit.
The exact signed bytes, hash and nonce are journaled before broadcast. An unknown
outcome blocks new writes. Recover its exact finalized transaction:

```powershell
uv run --locked python scripts/onchain_art_testnet.py recover data/testnet-rehearsals/full-lab data/onchain-prototypes/genesis-idart1 --plan-sha256 REVIEWED_PLAN_SHA256 --tx-hash EXACT_SAVED_HASH
# If submission was rejected before inclusion, resolve its cause, then optionally
# rebroadcast ONLY those identical bytes; do not sign another transaction.
uv run --locked python scripts/onchain_art_testnet.py recover data/testnet-rehearsals/full-lab data/onchain-prototypes/genesis-idart1 --plan-sha256 REVIEWED_PLAN_SHA256 --tx-hash EXACT_SAVED_HASH --rebroadcast-exact --send
```

The bootstrap uses the existing CLI journal and verifies its four exact actions.
nearcore's transaction view returns the deployment's code hash rather than full
WASM; recovery binds it to the reviewed bytes and reads back the account code.
The narrowly guarded `invalidate-pending` command exists for the initial legacy
CLI's no-hash preparation failure. It requires unchanged signer nonce and an
absent edition, then consumes that sole possible nonce with a zero-deposit
`get_config` call. It is not a reset of artwork or a general permission to clear
an unknown transaction.

## Site configuration and independent recovery

After verification, configure these public values in the isolated profile and
restart the API:

```dotenv
ONCHAIN_ART_CONTRACT=art-v1.id-operator.testnet
ONCHAIN_ART_TOKEN_ID=ONCHAIN-PROTOTYPE-000001
EXPECTED_ONCHAIN_ART_CODE_HASH=REVIEWED_WASM_SHA256
```

Open `/demo/onchain`. The reader pins one finalized block, checks code and keys,
then obtains `get_static_svg` or `get_animated_svg` and verifies its stored hash.
The browser verifies those bytes again before showing them as an SVG image.
Downloads include each view and the packed recipe. Errors do not fall back to
hosted artwork or label a local preview as onchain.

Independent clients can call `get_edition`, `get_recipe_chunk`,
`get_static_svg`, `get_animated_svg` and the standard NFT methods directly.
Use `get_recipe_chunk` in 16,384-byte intervals; concatenate the decoded chunks
and compare SHA-256. The included native example renders the same packed bytes
offline. Contract source and dependencies are provided for independent builds.
