# Monthly payouts and rollover verified — 14 November 2026

December 2026 and January 2027 were closed and paid on public NEAR testnet.
The isolated lab clock is now frozen at **1 February 2027, 00:02 UTC** across
NFT, auction and marketplace contracts. These are controlled rehearsal dates.
Contract code, production configuration and mainnet accounts were not changed.

## Observed results

| Cycle | Eligible NFT | Fixed beneficiary | Prize delivered | Final status |
|---|---|---|---:|---|
| December 2026 | ECHO-000004 | `iddeployertest.testnet` | 1.2 NEAR | Drawn / Paid |
| January 2027 | ECHO-000008 | `idtester1.testnet` | 0.88 NEAR | Drawn / Paid |

The fresh preflight found an early withdrawal on ECHO-000007 that occurred after
the earlier auction report. Its 1.04 NEAR original allocation had already paid
0.416 NEAR to its owner. This run preserved that choice: edition 7 received no
January ticket, and its 0.624 NEAR remainder was collected into February.
February remains Open with **0.624 NEAR, zero eligible NFTs**, one expected and
one received contribution, and no pending source. Rollover adds funds without
granting the exited NFT a new ticket.

Both closed cycles had exactly one eligible entry. They therefore exercised the
contract's single-entry selection and payment path: **no random choice or BLS
proof submission was needed onchain**. A live draw between multiple eligible
NFTs remains an acceptance scenario. This run did not undo an exit, manufacture
eligibility, submit bids or transfer a collector's NFT to create extra entries.

## Finalized transactions

| Operation | Transaction |
|---|---|
| Close December | [5pLKN2DeE8WbyN3Nr5P7pmSw9Eqxei12ZkxQPHtp51Zm](https://testnet.nearblocks.io/txns/5pLKN2DeE8WbyN3Nr5P7pmSw9Eqxei12ZkxQPHtp51Zm) |
| Collect edition 4 | [ArfPCLHZXUg2mAW9XtReCRhvNZieYvPeetdVczEweSCk](https://testnet.nearblocks.io/txns/ArfPCLHZXUg2mAW9XtReCRhvNZieYvPeetdVczEweSCk) |
| Select December winner and pay | [HXd3x6Wwm9QKjvFCQMo7TY6MQBuM4SNWKxNdPvqig9Mm](https://testnet.nearblocks.io/txns/HXd3x6Wwm9QKjvFCQMo7TY6MQBuM4SNWKxNdPvqig9Mm) |
| Close January | [49FQbgD5n1WwNif1G9PQ4WSFbn6ySFcWGJkPwWaHpefa](https://testnet.nearblocks.io/txns/49FQbgD5n1WwNif1G9PQ4WSFbn6ySFcWGJkPwWaHpefa) |
| Collect edition 7 into February | [FBkXM551w99eB6HC9NS4rSePV6baGASLp4H81BLDnUqV](https://testnet.nearblocks.io/txns/FBkXM551w99eB6HC9NS4rSePV6baGASLp4H81BLDnUqV) |
| Collect edition 8 into January | [JCKzxxZgZxNsAS1eJPotiHnQY69ZvonrECkkGPUkT9Ne](https://testnet.nearblocks.io/txns/JCKzxxZgZxNsAS1eJPotiHnQY69ZvonrECkkGPUkT9Ne) |
| Select January winner and pay | [AJD8nUpdh1NLbDFZuWzEXJUhWxeBFwAjuGKGbw2W6fRn](https://testnet.nearblocks.io/txns/AJD8nUpdh1NLbDFZuWzEXJUhWxeBFwAjuGKGbw2W6fRn) |

Each operator transaction was independently checked at FINAL for its exact
signer, receiver, method, arguments and zero attached deposit, including
descendant execution failures. Code hashes, policy bindings, testnet chain
identity and synchronized lab clocks were checked before execution. Calls used
the existing journaled CLI/keychain workflow and the maintenance methods used
by the production keeper, not an AI-selected recipient or an unjournaled signer.

The exact successful native-transfer receipts were also fetched:

| Recipient | Amount | Receipt ID |
|---|---:|---|
| `iddeployertest.testnet` | 1.2 NEAR | `CvDEa3S35wFzQWbKfoNLKXUGr7PCkRxjeDdxHeeSF9g4` |
| `idtester1.testnet` | 0.88 NEAR | `AnHs9CNJYjmEG6nNfHbnmfZ1QgsVmgiyhtyWdTxAFWu2` |

Each receipt's predecessor is `id-nft.testnet`, its receiver matches the frozen
beneficiary, and its sole transfer amount matches the recorded prize. Recipient
native balances increased by exactly those amounts, both immediately around
their draws and across the entire acceptance run. Gas was paid separately by
the operator. Both payouts completed on their first attempt.

## Accounting and recovery checks

- All three funded edition allocations were collected once; their vault
  available amounts and coordinator remaining amounts are zero, and each
  vault's collection payment reports Paid.
- NFT ownership is unchanged. The team-owned genesis and two no-bid returns
  remain unfunded and were excluded from both draws.
- Recorded primary proceeds conserve exactly: **3.9 = 0.78 treasury + 2.08
  monthly prizes + 0.416 prior early withdrawal + 0.624 February reserve**, in
  NEAR. Checks used integer yoctoNEAR, not floating-point arithmetic.
- Treasury totals and credits were unchanged by this run. Coordinator liability
  is exactly 0.624 NEAR, matching February's retained pot. `next_close=202702`.
- Repeated `draw_month` and `pay_month` calls were rejected in read-only RPC
  simulations for both paid cycles, and subsequent finalized month views were
  unchanged. The runtime returned a WASM unreachable trap rather than the Rust
  assertion text. No duplicate transaction was signed or duplicate prize paid.
- No operator action remains with an unknown outcome. Private snapshots,
  receipt bodies, journals and verification scripts remain ignored locally.

## Site and contract validation

The live frontend proxy at `http://127.0.0.1:3004` returned fresh monthly totals
matching all three cycles, the correct paid beneficiaries, January's one early
withdrawal and February's incoming rollover. `/economy`, `/my-collection` and
`/drops` returned HTTP 200. This is API/route verification, not browser visual or
wallet-signing acceptance.

The current lab NFT contract's **30 native tests passed**, including real drand
BLS verification, rejection of an altered round and multi-entry selection in
the five-sales/two-exits accounting scenario. That native scenario substitutes
the historical beacon round only in test state; it does not establish a live
multi-entry testnet draw. The deployed lab also uses known historical round
6624326. Production derives its fixed future round and has no lab clock methods.

An initial native build attempt lacked the Visual C++ environment/NASM setting;
rerunning with the existing `vcvars64.bat` and prebuilt-NASM configuration passed.
Initial Python RPC checks needed the Windows trusted certificate store; TLS
verification remained enabled. No dependency or runtime code change was needed.

Marketplace royalty distribution, live multi-entry randomness, managed-cloud
operation and independent contract review remain separate acceptance work.
