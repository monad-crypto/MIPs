---
mip: 20
title: Linear Code-Loading Costs
description: Price cold code loads linearly in code size, tracking loaded code in a separate warm set
author: Category Labs (@category-labs)
discussions-to: https://forum.monad.xyz/t/mip-20-linear-code-loading-costs/593
status: Draft
type: Standards Track
category: Core
created: 2026-11-04
---

## Abstract

In Monad, operations that load code (calls, `EXTCODESIZE`, `EXTCODECOPY`, etc.) from the database are priced at a flat rate, independent of code size, intended to cover both the database I/O and the cost of jumpdest analysis on the loaded code: contract size is capped at 128KiB ([MIP-2](./MIP-2.md)), so any such operation performs a bounded amount of work.

This MIP proposes a change to gas pricing for these operations that replaces constant pricing with a linear regime, where the cost to load cold contract code from the database is linear in the size of the contract code. Because this cost is charged before the code is loaded, clients must be able to determine the size of contract code without loading it; `EXTCODESIZE`, which requires only the size, is therefore priced independently of code size.

To support this, the MIP introduces a set of warm code hashes, separate from warm accounts; reprices `COLD_ACCOUNT_ACCESS_COST` to cover only the account access and code size lookup; and charges the cost of loading the code for a transaction’s `to` address at the start of execution.

## Motivation

At present, all cold code loads are priced identically, no matter how large the contract is: a cold access to a contract 1 byte in size costs 10,100 gas, the same as a 128KiB contract. This presents several issues that can be addressed by linearly pricing code loads:

- **Pricing of small contracts:** the flat pricing charges calls and accesses to small contracts for the code loading and analysis work required by the largest permitted contract. Users of small contracts pay for more work than their usage requires.
- **Alignment of costs:** current code-loading costs are not well-aligned with the actual work performed by the client. [MIP-3](./MIP-3.md) used benchmarking of EVM memory costs to align them with hardware performance: principled alignment work of this kind is also possible with code loading and analysis.
- **Future relaxation of code size limits:** any future proposal to increase the code size limits on Monad must address these pricing issues. Doing so in a standalone MIP simplifies the design process for this intended future work.

## Specification

### Current constants

| Constant | Value |
| --- | --- |
| `WARM_STORAGE_READ_COST` | 100 |
| `COLD_ACCOUNT_ACCESS_COST` | 10,100 |

### New constants

| Constant | Value |
| --- | --- |
| `COLD_ACCOUNT_ACCESS_COST` | TBD |
| `CODE_LOAD_BASE_COST` | TBD |
| `CODE_LOAD_WORD_COST` | TBD |

The new value of `COLD_ACCOUNT_ACCESS_COST` as specified in this MIP replaces the old value.

### Code-loading Operations

Define the following to be “code-loading” operations that require the client to load the code for a particular contract from state. Each operation loads the code for one address:

- `CALL`, `CALLCODE`, `DELEGATECALL` and `STATICCALL` load the code for the code address (the `address` argument to the call).
- `EXTCODECOPY` with a non-zero `size` loads the code for the targeted address. With `size` zero, or with `offset` greater than or equal to `|C|`, no code is loaded: the copied bytes are all zero.
- The `to` address for a transaction has its code loaded.

If the code address of a call, or the `to` address of a transaction, holds an EIP-7702 delegation indicator, the code of the delegation target is loaded instead. `EXTCODECOPY` does not follow delegation indicators. Reading the delegation indicator itself is part of the account access and is not a code load.

If the code to be loaded is empty (including for precompile addresses), the operation does not load code.

The address whose code is loaded, after following any delegation indicator, is the operation’s *loaded address*. The code hash recorded in the loaded address’s account is the operation’s *loaded code hash*.

### Warm Code Set

Add a new set `A_c` to the accrued substate, analogous to the accessed-address and accessed-storage-key sets `A_a` and `A_K` (Yellow Paper §6.1, introduced by EIP-2929). This set contains the hashes of warm (previously loaded) code. `A_c` begins empty at the start of a transaction, and code hashes are added to it:

- the loaded code hash of a code-loading operation (see [Code-loading Operations](#code-loading-operations)), or
- the hash of the deployed code, when a contract is successfully created.

Changes to `A_c` are rolled back when a frame reverts or halts exceptionally.

Access lists do not add to `A_c`.

### Pricing

On code-loading operations for code `C`, if the loaded code hash is not in `A_c`, charge the following additional gas `G_code` after the account access cost (warm or cold):

```txt
G_code = CODE_LOAD_BASE_COST + CODE_LOAD_WORD_COST * ceil(|C| / 32)
```

Once `G_code` has been charged, the loaded code hash is added to `A_c`. If the loaded code hash is already in `A_c`, `G_code` is not charged.

Code must not be loaded in full until `G_code` has been charged. For calls, `G_code` is charged before the gas forwarded to the callee is computed under the 63/64 rule of EIP-150. If the caller does not have sufficient gas to pay for the code load, the operation fails with out-of-gas and the code is not loaded.

At the start of a transaction, the rules above apply to the code loaded for the transaction’s `to` address (or its delegation target): `G_code` is deducted from the gas remaining after intrinsic gas, before execution of the code begins, and the loaded code hash is added to `A_c`. If the remaining gas is less than `G_code`, execution halts exceptionally with out-of-gas, with the same effects as any other exceptional halt of the top-level call.

## Rationale

### Gas Benchmarking

**TODO** (pending benchmarking and selection of pricing constants).

### Determining Code Size Before Loading

`G_code` depends on `|C|`, and is charged before the code is loaded so that an operation without sufficient gas to pay for a load never performs it. Clients must therefore be able to determine `|C|` without loading `C` in full. The cost of determining `|C|` is fixed, independent of code size, and is covered by `COLD_ACCOUNT_ACCESS_COST`; `CODE_LOAD_BASE_COST` covers the fixed overhead of the code load itself.

For the same reason, `EXTCODESIZE` is not a code-loading operation: it requires only `|C|`, so it is priced as an account access, independently of code size.

### Separate Warm Code Set

Maintaining a separate warm code set is necessary to distinguish between operations that load contract code and those that only load accounts. If warming an account also warmed its code, a `BALANCE` followed by a `CALL` would load the code for an account at no cost, regardless of its size.

Newly created contract code is warmed because the creator already has the code (to deposit in state).

### Keying Warm Code by Code Hash

`A_c` is keyed by code hash rather than by address because the work that `G_code` prices depends on the code, not on the account that holds it. Contract code is content-addressed in state: an account records only the hash of its code, and the code is stored under that hash. Once code with a given hash has been loaded and analysed during a transaction, a client can serve every other account with the same code hash from that copy, with no further I/O or jumpdest analysis. Keying by address would charge for this work again for each account, overcharging the common pattern of deploying identical runtime code at many addresses (for example, factory-deployed pool contracts called in sequence by a multi-hop swap).

Keying by code hash adds no work for the client: the code hash is part of the account record, which the account access has already read before `G_code` is computed. It also gives contract creation a direct rule: the hash of the deployed code is known when the code is deposited in state, and adding it to `A_c` warms that code for every account that holds it.

The trade-off is that the cost of a code-loading operation depends on which code, rather than which addresses, the transaction has already loaded, so gas cost cannot be predicted from the set of accessed addresses alone. Gas estimation, which executes the transaction, is unaffected.

### Code Changes Within a Transaction

At present, an account’s code can change within a transaction only through contract creation. Mechanisms have been proposed that would let an existing account’s code change mid-transaction; for example, the `SETCODEFROM` instruction of [EIP-8298](https://github.com/ethereum/EIPs/blob/f4a9f9655ee88ed923ceac6cb6271820477e11c5/EIPS/eip-8298.md) sets the current account’s code hash to that of another deployed account. This MIP is designed to remain sound if such a mechanism is adopted.

Because `A_c` is keyed by code hash, a change to an account’s code needs no special handling: a later code-loading operation on that account reads the new code hash from the account, and charges `G_code` unless that hash is already in `A_c`. Warmth cannot carry over from the old code to the new. Keying by address would instead require removing an address from the warm set whenever its code changed. Similarly, the code size lookup is unaffected, provided that `|C|` is determined from the code hash recorded in the account at the time of the operation.

Such a mechanism would not need a new warming point, and should not add one. Adopting code by reference to its hash does not load it (the cost of `SETCODEFROM` is independent of the adopted code’s size), so warming the adopted hash would allow a later call to load the code without paying `G_code`.

The one rule that would need refining is warming on contract creation. That rule is justified because the creator supplies the deployed code, which the client has in hand to hash and deposit in state. A creation that instead adopts existing code, as EIP-8298 permits during initcode, deposits nothing, and should not warm the adopted code hash: the creation warming point should apply only to code deposited from initcode return data.

### Interaction with Access Lists

Access lists have a price fixed at validation time, and cannot depend on `|C|`. They therefore cannot warm contract code as well as account state.

### Delegation Indicators

Resolving a delegation indicator charges only for the code loaded for the pointed-to account, rather than for the delegated EOA’s own code as well. Reading the indicator is treated as part of the account access because it is a fixed-size, 23-byte read: an account whose code is not exactly 23 bytes cannot hold a delegation indicator, and because [EIP-3541](https://eips.ethereum.org/EIPS/eip-3541) prevents deployed code from beginning with `0xEF`, 23 bytes of code beginning `0xEF0100` can only be a delegation indicator. Implementations should therefore avoid loading code in full during delegation resolution when the delegating account does not have exactly 23 bytes of code.

### Charging the Transaction `to` at Execution

Intrinsic gas is fixed at validation time, and cannot depend on `|C|`. The cost of loading the code for the `to` address therefore cannot be charged before execution begins.

### Intrinsic Gas Unchanged

This MIP does not change the 21,000 gas intrinsic cost of a transaction. That cost was set before code loading was metered, and neither Ethereum nor Monad currently charges for loading the code of a transaction’s `to` address. Charging `G_code` at the start of execution therefore prices work that was previously unpriced, rather than charging twice for work that intrinsic gas already covers.

Intrinsic gas does implicitly cover a cold access to the `to` address, whose price this MIP changes through `COLD_ACCOUNT_ACCESS_COST`. Adjusting intrinsic gas to match would require separating 21,000 into its components (signature recovery, sender and recipient account access, value transfer, and so on), which is the scope of [EIP-2780](https://eips.ethereum.org/EIPS/eip-2780); adopting EIP-2780 is not currently planned for Monad. Without that separation, any reduction here would not be derived from benchmarking. This MIP leaves intrinsic gas for a separate proposal, so its change remains additive: transactions to accounts without code are unaffected, and transactions to contracts pay `G_code` for the code they load.

### `EXTCODECOPY` Pricing

The pricing for `EXTCODECOPY` is set the same as the other code-loading operations for consistency: even though copying account code does not entail jumpdest analysis, there is still a per-byte cost for loading the code from state.

An `EXTCODECOPY` whose `offset` is at or beyond the end of the code reads no code bytes, so it is not a code load: it neither charges `G_code` nor adds to `A_c`. Not warming is required for soundness, not just accuracy: if such an `EXTCODECOPY` warmed the code without charging for it, a following call to the same code would load it for free. A copy that overlaps the code at all is a code load and is charged for the whole code, consistent with every other code-loading operation.

### Comparison with EIP-7907

This MIP is similar in substance to many elements of EIP-7907’s proposed design for Ethereum. The main differences are:

- This MIP does not raise the code size limit. EIP-7907 originally combined metering with a limit increase; the increase has since moved to [EIP-7954](https://eips.ethereum.org/EIPS/eip-7954).
- No “free threshold” for small contracts is specified here. EIP-7907 exempts the first 24KiB of code so that no existing contract becomes cheaper to load; this MIP instead prices small contracts by the work they require (see Motivation).
- No change to the account state is proposed to track code size explicitly (`codesize` in EIP-7907). Current implementations of the Monad protocol are able to determine code size cheaply from database metadata without loading full contract code.
- The pricing constants in this MIP are determined from benchmarking specific to existing Monad clients, and are not derived from Ethereum performance modelling.

## Backwards Compatibility

This MIP changes the gas cost of existing operations. The magnitude of each change depends on the final pricing constants (**TODO**):

- Calls and `EXTCODECOPY` on cold code are charged in proportion to code size. Loads of small contracts may become cheaper than the current flat cost, and loads of large contracts more expensive.
- `BALANCE`, `EXTCODESIZE`, `EXTCODEHASH` and calls to accounts without code are affected only by the change to `COLD_ACCOUNT_ACCESS_COST`.
- Transactions whose `to` address has code are charged `G_code` at the start of execution; no such charge applies today.
- Contracts that store data as contract code and read it with `EXTCODECOPY` are charged according to the size of the data contract.

Transactions and contracts that hard-code gas budgets rather than estimating them may run out of gas where they previously succeeded. Because `G_code` for a call is charged to the caller before the 63/64 rule is applied, gas limits passed to individual calls do not need to cover the callee’s code load; budgets that cover nested code loads, such as fixed transaction gas limits or relayed calls, are affected. Gas estimation accounts for the new costs.

## Test Cases

**TODO**

## Reference Implementation

This MIP is implemented on branch **TODO** of the Monad reference executable specification.

## Security Considerations

The pricing constants are chosen so that the gas charged for each affected operation covers the work it requires of the client: the fixed cost of an account access and code size lookup, the fixed overhead of a code load, and the per-word cost of loading and analysing code (see Gas Benchmarking).

**TODO** (pending selection of pricing constants): if the cost of a cold call falls below the 2,300 gas stipend, discuss the effect on contracts that rely on the stipend.

## Acknowledgements

The proposals in this MIP are based on a previous EIP document:

- [EIP-7907](https://github.com/ethereum/EIPs/blob/b3a1f7ba0554f57c5d892028f42d6bc8716bfb88/EIPS/eip-7907.md) (@charles-cooper, @qizhou, @lightclient, @rakita, @benaadams)

This MIP differs from EIP-7907 in that it does not raise the code size limit, does not exempt a free threshold of code from metering, and does not add code size to the account state (see Comparison with EIP-7907).

## References

- [MIP-2: Increase Contract Code Size Limit](./MIP-2.md)
- [MIP-3: Linear Memory](./MIP-3.md)
- [EIP-150: Gas cost changes for IO-heavy operations](https://eips.ethereum.org/EIPS/eip-150)
- [EIP-170: Contract code size limit](https://eips.ethereum.org/EIPS/eip-170)
- [EIP-2780: Reduce intrinsic transaction gas](https://eips.ethereum.org/EIPS/eip-2780)
- [EIP-2929: Gas cost increases for state access opcodes](https://eips.ethereum.org/EIPS/eip-2929)
- [EIP-3541: Reject new contract code starting with the 0xEF byte](https://eips.ethereum.org/EIPS/eip-3541)
- [EIP-7702: Set Code for EOAs](https://eips.ethereum.org/EIPS/eip-7702)
- [EIP-7907: Meter Contract Code Size](https://github.com/ethereum/EIPs/blob/b3a1f7ba0554f57c5d892028f42d6bc8716bfb88/EIPS/eip-7907.md)
- [EIP-7954: Increase Maximum Contract Size](https://github.com/ethereum/EIPs/blob/f1ade090fd315895461fc3e249cb1a675aeb55a9/EIPS/eip-7954.md)
- [EIP-8298: SETCODEFROM Code Reuse Instruction](https://github.com/ethereum/EIPs/blob/f4a9f9655ee88ed923ceac6cb6271820477e11c5/EIPS/eip-8298.md)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
