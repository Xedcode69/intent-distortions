# Immutable onchain study verified — 14 November 2026

One separate onchain-format NFT was minted on public NEAR testnet and recovered
using chain reads alone. The saved historical genesis and the existing financial
contracts were preserved. This is an isolated format prototype, not a switch of
the production weekly publisher or a mainnet deployment.

| Item | Verified value |
|---|---|
| Collection contract | [`art-v1.id-operator.testnet`](https://testnet.nearblocks.io/address/art-v1.id-operator.testnet) |
| NFT | `ONCHAIN-PROTOTYPE-000001` |
| Owner | `id-team.testnet` |
| Title / family | Echo of the Hub / Crystalline |
| Artistic direction | Reused first accepted NEAR AI Cloud response from the saved historical run |
| Source activity | 130,086 contributing successful records; 37 recognized source networks; 615 network routes |
| Frozen geometry | 4,219 shapes |
| Packed recipe | 100,644 bytes |
| Canonical static / animated SVG | 447,889 / 634,013 bytes, generated from the same onchain record |
| Optimized shared renderer WASM | 298,352 bytes, down from 519,084 before Binaryen 125 |
| Access keys / NFT supply | Zero / one |

The packed recipe is approximately 80.4% smaller than the source's 513,879-byte
SVG. Both generated views share it; no animation frames or duplicate image
payloads are stored. The contract contains the complete integer-only SVG
renderer, including native animation instructions. No IPFS, hosted image,
external font, JavaScript renderer or new AI request is required for recovery.

## Immutable commitments

| Commitment | SHA-256 |
|---|---|
| Deployed renderer code | `d9bac8e086fc4a43851abec3d954cf77f1cf7e04a101f369ae085d916e347d6a` |
| Recipe | `0ba492658a79cbfb70ef2ecdb34cafec497f3c1a2f7e03d97fb7edf4521225ea` |
| Static SVG | `b870866d3f2eded46854edaf3f941ddd8f8bdf3d820ca5a413aa253893b2424b` |
| Animated SVG | `4689ad3685cbd2a9a2a207e004421d92bc56803b66f687b8d70c0dbb8881cbda` |
| Edition binding | `30ed8232a1914eee4e4fe67b4d17fbdd1726be53b74f3bf110601d927b0fb7eb` |
| Source provenance | `2839147a67384e9cb1ce73038e9e9cc9894a39c54e1813689e086a4641d07612` |

The account was created with exactly CreateAccount, Transfer, DeployContract and
initialization, with no AddKey action. Its code exposes no upgrade, deletion,
key-management, arbitrary-call or artwork-replacement method. The build's export
allowlist and finalized account code hash agree. Subsequent views show no access
keys. NFT transfers change ownership without rewriting the artistic record.

The static composition is a new vector-format study derived from the source
scene; it does not claim the original PNG's pixel hash. Coordinates, sizes and
strokes are fixed to integer thousandths. The accepted AI response, source
commitments, artistic traits and motion controls are retained onchain. Existing
artistic traits describe the source scene generator; NFT extra/config identify
the new onchain format separately.

## Public execution evidence

| Operation | Finalized transaction |
|---|---|
| Create keyless account, deploy and initialize | [Bx2CMbQox5CC9qTkrckJnSq2tYokUmkY3uPEvgbG2kLC](https://testnet.nearblocks.io/txns/Bx2CMbQox5CC9qTkrckJnSq2tYokUmkY3uPEvgbG2kLC) |
| Bind metadata, recipient and recipe hash | [Dk5wo2Q1bNBfGweVsjA4AgYspvSnkMrpj26yHL8fNzPK](https://testnet.nearblocks.io/txns/Dk5wo2Q1bNBfGweVsjA4AgYspvSnkMrpj26yHL8fNzPK) |
| Seal both views and mint | [AGrn4ChzNKJNsGr25Gx6w2z3B35b87Hg9vZTPqR2PWoa](https://testnet.nearblocks.io/txns/AGrn4ChzNKJNsGr25Gx6w2z3B35b87Hg9vZTPqR2PWoa) |
| Attempt to overwrite sealed geometry — rejected | [91aTVBKhDDeAxwmdWGWUiEPtvAKpeod8mTV8csATdfEU](https://testnet.nearblocks.io/txns/91aTVBKhDDeAxwmdWGWUiEPtvAKpeod8mTV8csATdfEU) |
| Attempt to mint it again — rejected | [7QhHSkQDSYb74V8v5ApGa73AASXeJHihqRhd5ccyGhr6](https://testnet.nearblocks.io/txns/7QhHSkQDSYb74V8v5ApGa73AASXeJHihqRhd5ccyGhr6) |

Seven append-only upload transactions filled the committed recipe at exact
16,384-byte offsets; the last chunk held the remainder. Every successful action
was checked against FINAL receipt signer, receiver, method, arguments and
deposit, including descendant failures. The mint emitted NEP-171 and art-sealed
events. Both deliberate negative tests finalized with failure; supply stayed
one and the entire artistic record stayed unchanged.

Standard `nft_token` returns the static SVG as an embedded data URL with its
matching media hash, plus the inherited artistic traits. Team ownership, inline
media bytes and traits were independently checked. Each recovered recipe chunk
and both SVGs match the prepared local bytes exactly. Recovery was verified at
finalized block 277649764, followed by the later immutability checks.

## Cost and operational findings

The final contract occupies 405,103 bytes. Its per-edition storage delta is
106,465 bytes, approximately 1.06465 NEAR of storage balance at the queried
testnet rate of 10^19 yoctoNEAR per byte. Shared renderer and initial state are
additional one-time storage. The 1.24644 NEAR upload prepayment exceeded the
recorded delta by 0.18179 NEAR, returned by the successful seal's refund promise.
Storage balance is not the same as consumed transaction fees.

The node's transaction balance check needed more gas headroom than the initial
runner budget. A [0.4 test NEAR budget transfer](https://testnet.nearblocks.io/txns/4E9WMv6fMfmx49L3ghb54Cnjt5M6EZn3CK2vEUE8zfQw)
from the configured deployer funded the operator. No treasury, prize pool or
collector funds were used.

The initial CLI sender returned no transaction ID for a rejected preparation.
Before another preparation was allowed, unchanged signer nonce and absent draft
were verified; a [zero-deposit read transaction](https://testnet.nearblocks.io/txns/J1uUJxJgwBXkVvduBbuQHULajQ3vHjrHmmohEiKjERJN)
consumed its sole possible nonce. That old call cannot execute later. The runner
now signs in display-only mode, validates the entire serialized intent and
journals exact bytes/hash/nonce before broadcasting. The funded preparation was
recovered by rebroadcasting the identical saved bytes, not a different signed
transaction. No unknown operator outcome remains.

An earlier [200 Tgas seal](https://testnet.nearblocks.io/txns/AX8u8jxuuYMaY94TBRpDwEC78Jk1tx984hYjERyrnDnA)
exhausted prepaid gas and reverted with the draft still unsealed. The same
record sealed successfully at 300 Tgas. Its successful execution receipts burned
approximately **297.6 Tgas**, leaving little headroom. **Optimize the renderer or
stage view validation in a new immutable version before enabling larger weekly
editions in production.** This deployed study cannot be upgraded to do that.

## Interface and regression validation

The isolated site runs at `http://127.0.0.1:3004/demo/onchain`. Still/In motion
controls load hash-verified SVGs from the pinned contract. Each view and the raw
recipe can be downloaded. The original Demo links to the new study. Provenance
and technical details are collapsed. The prototype is clearly marked as a
separate testnet collection with no auction or reward allocation; the primary
collection's marketplace and owned-artwork views keep their existing bindings.

Live proxy checks passed for both SVGs, recipe bytes, CSP/download headers and
the Demo, Drops and Rewards routes. December and January prizes remain Paid;
February's 0.624 NEAR reserve is unchanged. API signing remains disabled.

- Python: **225 passed, one PostgreSQL skip**; upstream AnyIO deprecation warning.
- Rust: **12 new onchain contract tests**, plus the unchanged workspace suite.
- JavaScript: **37 passed** across frontend, signer and educational demo.
- Production frontend build and TypeScript: passed.
- Original fixture verification: passed. Saved real-data source preparation also
  passed full provenance/statistics/scene/PNG replay before export.
- Recovered static SVG: rendered independently and visually inspected.
- Browser access host was unavailable; page-layout/mobile inspection, animated
  playback/performance and wallet/indexer display acceptance remain unverified.

Only source, tests, public configuration examples and this evidence are intended
for Git. Raw captures, prepared artwork, CA bundles, private profiles, signed
transaction journals, receipt bodies and tool binaries remain ignored. See the
[format and operator runbook](../ONCHAIN_ART.md).
