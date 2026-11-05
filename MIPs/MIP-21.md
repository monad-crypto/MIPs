---
mip: 21
title: Large Contract Deployment Opcode
description: Add an extension opcode that deploys contracts of up to 256KiB, paying part of the code deposit in MON
author: Category Labs (@category-labs)
discussions-to: https://forum.monad.xyz/t/mip-21-large-contract-deployment-opcode/594
status: Draft
type: Standards Track
category: Core
created: 2026-11-05
requires: 7, 20
---

## Abstract

Currently, the size of contracts deployed on Monad is bound by the 30M transaction gas limit. The state deposit cost of 200 gas per byte places a hard limit of 150,000 bytes (~146KiB) on deployed contract size, even before accounting for other sources of gas consumption. Consequently, the protocol currently limits contract deployments to 128KiB with no room to raise this limit under the standard deployment mechanism.

This MIP proposes a new deployment route that allows state deposit costs to be paid partly in MON from the deploying account’s balance, partially separating the state deposit cost from the transaction’s individual gas limit. Doing so allows contracts of up to 256KiB to be deployed without altering bounds imposed by other parts of the protocol.

Execution of large contracts deployed following this MIP relies on the per-byte pricing for code-loading operations defined in [MIP-20](./MIP-20.md).

## Motivation

Developers whose contracts exceed the code size limit currently split them across multiple contracts, at the cost of additional call overhead, deployment complexity and audit surface:

- Proxy and library patterns, which move logic into separate contracts reached via `DELEGATECALL`.
- The Diamond pattern ([EIP-2535](https://eips.ethereum.org/EIPS/eip-2535)), which routes calls by function selector to any number of implementation contracts behind a single address.
- SSTORE2-style data contracts, which store large constant data as the code of auxiliary contracts and read it with `EXTCODECOPY`.

With code loading priced in proportion to code size (MIP-20), the remaining obstacle to larger contracts is that the code deposit must be paid as gas within a single transaction. This MIP removes that obstacle for contracts up to 256KiB, removing the need for these patterns at that size.

## Summary

Developers wishing to deploy a contract larger than 128KiB must do so via a new `CREATEBIG` opcode, rather than a contract-creation transaction or the `CREATE[2]` opcodes. `CREATEBIG` takes the same arguments as `CREATE2` plus an additional `max_deposit_value` argument, and derives addresses identically. The `value` argument retains its `CREATE2` meaning as an endowment to the new contract. Part of the code deposit is charged as gas; the remainder is charged in MON at the block’s base fee from the balance of the account executing `CREATEBIG`, capped by `max_deposit_value`, and burned. EOAs and Solidity contracts can deploy via a companion factory contract specified in [MRC-22](../MRCs/MRC-22.md).

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Parameters

| Parameter                   | Value                  |
| --------------------------- | ---------------------- |
| `CREATEBIG_SELECTOR`        | `0x02`                 |
| `MAX_DEPLOY_CODE_SIZE`      | `262144` (256KiB)      |
| `MAX_DEPLOY_INITCODE_SIZE`  | `368640` (360KiB)      |
| `CODE_DEPOSIT_COST`         | `200` (gas per byte)   |
| `PARTIAL_CODE_DEPOSIT_COST` | `80` (gas per byte)    |

### Extension Selector

| Extended Opcode | Mnemonic    | Immediates | Stack Input                                            | Stack Output |
| --------------- | ----------- | ---------- | ------------------------------------------------------ | ------------ |
| `0xAE 0x02`     | `CREATEBIG` | None       | `value`, `offset`, `size`, `salt`, `max_deposit_value` | `address`    |

The extended opcode is not followed by argument bytes. The byte following the selector is decoded as the next instruction.

### `CREATEBIG`

`CREATEBIG` behaves identically to `CREATE2`, except as specified below. In particular, the following are those of `CREATE2`: derivation of the new contract’s address from the deployer, `salt` and `keccak256(initcode)`; the increment of the deployer’s nonce; address collision rules (EIP-684); the call depth limit; the gas forwarded to the constructor (EIP-150); the constructor’s call frame environment; the prohibition on use in a static context; and Monad’s restrictions on contract creation from delegated EOA code.

The *deployer* is the account executing `CREATEBIG` (the value of `ADDRESS`). Under `DELEGATECALL` or `CALLCODE`, this is the delegating account.

`CREATEBIG` differs from `CREATE2` as follows:

1. If `size > MAX_DEPLOY_INITCODE_SIZE`, `CREATEBIG` halts exceptionally, in place of the initcode size limit applied to `CREATE2` (EIP-3860).
2. In place of the `CREATE2` check that the deployer’s balance is at least `value`, `CREATEBIG` checks that the balance is at least `value + max_deposit_value`, computed without overflow. If the check fails, `CREATEBIG` fails as `CREATE2` does when the balance is less than `value`. Otherwise, `max_deposit_value` is held in escrow as specified in [Deposit Escrow](#deposit-escrow).
3. The deployed code `R` may be up to `MAX_DEPLOY_CODE_SIZE` bytes, in place of the limit applied to `CREATE2`.
4. The code deposit is charged as specified in [Deposit Charging](#deposit-charging), in place of `CODE_DEPOSIT_COST` gas per byte.

`CREATEBIG` may deploy code of any size up to `MAX_DEPLOY_CODE_SIZE`, including code small enough to be deployed by `CREATE2`.

This MIP does not change the code size limit, initcode size limit or code deposit cost applied to `CREATE`, `CREATE2` or contract-creation transactions ([MIP-2](./MIP-2.md)).

A successful `CREATEBIG` is a contract creation for the purposes of MIP-20: the hash of the deployed code is added to the warm code set.

#### Stack Interface

`CREATEBIG` pops five items from the stack and pushes one. The first four inputs are identical to those of `CREATE2`, in the same order, with `max_deposit_value` appended below them.

| Stack     | Input               | Meaning                                                                                                                    |
| --------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `top - 0` | `value`             | Value transferred to the new contract, as in `CREATE2`                                                                     |
| `top - 1` | `offset`            | Memory offset of the initcode                                                                                              |
| `top - 2` | `size`              | Size of the initcode in bytes                                                                                              |
| `top - 3` | `salt`              | Salt used for address derivation, as in `CREATE2`                                                                          |
| `top - 4` | `max_deposit_value` | Value, in wei, held in escrow from the deployer’s balance; the maximum that may be charged for the value-paid code deposit |

| Stack     | Output    | Meaning                                                |
| --------- | --------- | ------------------------------------------------------ |
| `top - 0` | `address` | Address of the created contract, or `0` on failure |

As with `CREATE2`, memory is expanded to cover `[offset, offset + size)` if `size` is non-zero.

#### Deposit Escrow

If the balance and call depth checks pass, `CREATEBIG` deducts `max_deposit_value` from the deployer’s balance before the constructor runs, and holds it in escrow until `CREATEBIG` completes. The escrow is held by the `CREATEBIG` frame, not by any account, in the same way as the gas forwarded to the constructor. The deduction is not part of the constructor frame’s state changes, and is not undone if those state changes are reverted.

When `CREATEBIG` completes, after the constructor frame’s state changes have been committed or reverted, the escrow is settled:

- If the deployment succeeds, `deposit` (see [Deposit Charging](#deposit-charging)) is burned from the escrow, and the remaining `max_deposit_value - deposit` is credited to the deployer.
- If the deployment fails for any reason, including an address collision, the full `max_deposit_value` is credited to the deployer.

#### Deposit Charging

When the constructor returns successfully with code `R`, after the checks `CREATE2` applies to `R` (EIP-3541) and the size limit above:

1. Charge `PARTIAL_CODE_DEPOSIT_COST * |R|` gas from the gas remaining in the constructor frame.
2. Compute `deposit = (CODE_DEPOSIT_COST - PARTIAL_CODE_DEPOSIT_COST) * |R| * block.basefee`.
3. If `deposit > max_deposit_value`, the deployment fails.
4. Otherwise, `deposit` is charged from the escrow and burned, as specified in [Deposit Escrow](#deposit-escrow).
5. Install `R` as the code of the new contract, and push its address.

Because the deposit is charged from the escrow, it cannot fail because the constructor reduced the deployer’s balance, for example by calling back into it.

#### Failure Handling

Failures follow `CREATE2`:

- If `size > MAX_DEPLOY_INITCODE_SIZE`, or `CREATEBIG` is executed in a static context, the current frame halts exceptionally.
- If the initial balance check fails, or the call depth limit is reached, `CREATEBIG` pushes `0` without running the constructor or taking the escrow, as `CREATE2` does.
- If the constructor reverts or halts exceptionally, `CREATEBIG` pushes `0`, with return data and remaining gas handled as for `CREATE2`.
- If the deployment fails after the constructor returns (an invalid code prefix, `|R| > MAX_DEPLOY_CODE_SIZE`, insufficient gas at Deposit Charging step 1, or step 3), it fails as `CREATE2` does when the code deposit cannot be paid: all state changes made by the constructor frame are reverted, the gas forwarded to it is consumed, the return data is empty, and `CREATEBIG` pushes `0`. No deposit is charged.

In every failure case after the escrow is taken, the escrow is returned to the deployer in full.

### Gas Costs

`CREATEBIG` charges the same gas as `CREATE2`, other than for the code deposit:

- 32,000 base cost.
- 6 gas per word of initcode for hashing, and 2 gas per word of initcode for initcode analysis (EIP-3860).
- Memory expansion for `[offset, offset + size)`, as defined in [MIP-3](./MIP-3.md).
- `PARTIAL_CODE_DEPOSIT_COST` gas per byte of deployed code, in place of `CODE_DEPOSIT_COST`, charged as specified in [Deposit Charging](#deposit-charging).

The value-paid portion of the deposit is not charged as gas, and does not count towards the block gas limit.

## Rationale

### New Opcode vs. Amending `CREATE2`

An alternative design would raise the code size limit for `CREATE2` and charge the value-paid portion of the deposit implicitly for code larger than 128KiB. This MIP instead introduces a new opcode, for the following reasons:

- **Draining existing contracts:** if the deposit were charged from the creating contract’s balance, any existing factory that executes caller-supplied initcode would pay the deposit for code returned by that initcode. A caller could repeatedly deploy large contracts through such a factory and burn its balance, making contracts that are safe today vulnerable without any change to their code.
- **Base-fee-dependent endowments:** if the deposit were instead deducted from `CREATE2`’s `value`, the new contract’s balance would depend on the base fee at the time of inclusion. Constructors could not rely on their endowment, and factories that forward `msg.value` as an endowment would silently pass on less than intended.
- **No room for a cap:** `CREATE2`’s stack interface is fixed. A caller cannot bound the value it is willing to pay for the deposit, other than through `value` itself.
- **Divergence from Ethereum:** Monad already raises the code size limits applied by `CREATE2`, but only in cases where the same operation fails on Ethereum. Charging value for the deposit would give `CREATE2` a new kind of behavior that is not present on Ethereum, and could conflict with future Ethereum changes to code size limits or deposit pricing.
- **Auditability:** with a separate opcode, the ability of a contract to pay deposits in value is visible in its bytecode, rather than depending on the size of the code that a `CREATE2` happens to deploy.

A hybrid design would introduce a new opcode with exactly the stack interface of `CREATE2`, charging the value-paid portion of the deposit implicitly. Because such an opcode is opt-in, it avoids the draining, divergence and auditability concerns above. It still faces the other two: if the deposit is deducted from `value`, endowments depend on the base fee; if it is charged from the current account’s balance, nothing bounds the value charged. This MIP adds the `max_deposit_value` argument to avoid both, at the cost of one additional stack input.

An earlier version of this proposal used an enshrined precompile. A precompile executes in its own frame, so it must reproduce the semantics of `CREATE2` from its caller (address derivation, nonce handling, the constructor’s `msg.sender`, and restrictions on delegated callers) as special cases, and requires its own calling convention, error encoding and refund mechanism. An opcode executes in the creating contract’s frame and inherits all of these from `CREATE2`, leaving only the deposit charging to be specified.

The main cost of a new opcode is that existing compilers cannot emit it. This is addressed by the companion factory contract (see [Compiler Support](#compiler-support)).

### Explicit Deposit Payment

`CREATEBIG` separates the endowment from the deposit. `value` retains exactly its meaning in `CREATE2`: the new contract’s balance and the constructor’s `msg.value` do not depend on the base fee or on the size of the deployed code.

The deposit is funded from the deployer’s balance rather than from `value`. `CREATEBIG` holds `max_deposit_value` in escrow while the constructor runs and returns the unused portion when it completes, in the same way that MON for gas is deducted when a transaction begins and the unused portion is refunded at its end. The value that pays for the deposit therefore travels with the gas forwarded to the constructor: both are set aside when the constructor frame is created, are unavailable to the deployer while it runs, and are settled when it returns. A contract that wishes to fund the deposit from its caller, such as the companion factory, can do so explicitly from `msg.value`. Such a contract must return any value not charged to its caller, with the usual considerations for a value-bearing `CALL`; see the [Refund Mechanism](../MRCs/MRC-22.md#refund-mechanism) and [Refund Re-entrancy](../MRCs/MRC-22.md#refund-re-entrancy) sections of MRC-22.

`max_deposit_value` bounds the value charged. The deposit is priced at the base fee of the block in which the transaction is included, which is not known when the transaction is signed. The cap lets a deployer bound its exposure to base fee movement, and makes the maximum value a contract may spend on deposits explicit at each use of `CREATEBIG`, in the same way that a `CALL` makes the value it transfers explicit.

The deployer’s balance is checked against `value + max_deposit_value`, and the escrow taken, before the constructor runs, so that a deployment whose deposit cannot be paid fails before the constructor executes. An alternative would check the balance before the constructor runs and charge the deposit from it afterwards. This requires a second balance check when the deposit is charged, and allows a deployment to fail after its constructor has run because the constructor reduced the deployer’s balance. With the escrow, the constructor cannot spend the value set aside for the deposit, and the only post-constructor deposit failure is a deposit that exceeds `max_deposit_value`.

### Partial Value-paid Deposit

A simpler version of this design could charge the full code deposit cost from the deployer’s balance, rather than splitting it across gas and value as proposed in this MIP. However, doing so presents a denial-of-service vector whereby a single block could write approximately 1.01GiB to disk with no fee-market controls on blockspace: bytes paid for in value do not count towards block gas, so neither the block gas limit nor the base fee adjustment respond to them.

While the cost to write this much state would be the same as in the current protocol (approximately $435 at $0.02/MON and a base fee of 100 gwei), the full-value charging design allows that cost to be concentrated in a single block rather than spread across approximately 1,450 blocks in the current protocol.

The value of `PARTIAL_CODE_DEPOSIT_COST` was chosen to limit the per-block state growth as much as possible while still permitting 256KiB contracts to be deployed with appropriate gas headroom for initcode execution and calldata.

Charging the first 131,072 bytes of deployed code at `CODE_DEPOSIT_COST`, as for `CREATE2`, and only the remainder in value would fix the gas portion of the deposit for any deployment above 128KiB at 26,214,400 gas, which exceeds the gas available to the constructor frame when initcode for a maximum-size contract is supplied as calldata (see [Numerical Reasoning](#numerical-reasoning)).

#### Numerical Reasoning

The figures below assume a 30M transaction gas limit, a 150M block gas limit, 16 gas per byte of calldata, and memory pricing as defined in MIP-3. They exclude the code-loading charge defined in MIP-20 for the deploying contract’s own code, which is small for a minimal factory.

Consider a maximum-size deployment from an EOA through a minimal factory contract, with initcode of approximately the same size as the deployed code (`|initcode| ≈ |R| = 262,144`) passed as calldata. The gas consumed outside constructor execution is:

| Item                                                             | Gas        |
| ---------------------------------------------------------------- | ---------- |
| Transaction intrinsic cost                                       | 21,000     |
| Calldata (initcode and ABI encoding, 16 gas per byte)            | 4,196,928  |
| Factory execution (copying initcode to memory, memory expansion) | ~28,900    |
| `CREATEBIG` base cost                                            | 32,000     |
| Hashing and analysis (8 gas per word)                            | 65,536     |
| Deposit gas (`80 * 262,144`)                                     | 20,971,520 |

Of the 25,655,664 gas remaining when `CREATEBIG` executes, 1/64 is retained by the factory (EIP-150), and the constructor frame receives 25,254,795. The deposit gas is charged from this frame after the constructor returns, leaving approximately 4.28M gas for constructor execution. The retained gas (~400K) is sufficient for the factory to return any excess value to the caller.

At the maximum initcode size of 360KiB, calldata, copying and hashing costs rise, leaving approximately 2.57M gas for the constructor. A deployment made from a contract that reaches `CREATEBIG` through a further call frame (for example, a `DELEGATECALL` to the factory) loses a further 1/64 of its remaining gas, approximately 400K. Conversely, reserving approximately 4.5M gas for the constructor bounds the gas portion of the deposit at `(25,254,795 - 4,500,000) / 262,144 ≈ 79` gas per byte; the value of 80 leaves approximately 4.28M.

The maximum state that can be written per block (150M gas) is then:

| Charging model                                | Maximum state per block | Relative to current protocol |
| --------------------------------------------- | ----------------------- | ---------------------------- |
| Current protocol (`CREATE`, 200 gas per byte) | ~750KB                  | 1x                           |
| This MIP (80 gas per byte)                    | ~1.87MB                 | ~2.5x                        |
| Full-value deposit (0 gas per byte)           | ~1.01GiB                | ~1,450x                      |

The cheapest way to write code via `CREATEBIG` is a contract that executes it repeatedly with distinct salts and minimal initcode returning 256KiB of memory. Because code is stored by hash, each deployment must return distinct code to grow state, which the initcode can achieve by writing one distinguishing word before returning. Excluding the per-byte deposit gas, each such deployment costs approximately 36,000 gas: the 32,000 base cost, 4,096 for memory expansion in the constructor, and a small amount for hashing, constructor execution and loop overhead. No call, log or cold account access is required. With no gas charged per byte, approximately 4,100 deployments fit in a block, writing ~1.01GiB.

Under this MIP, each such deployment consumes approximately 21.01M gas. Seven such deployments fit in a block (1.75MiB), and the remaining ~2.95M gas can write a further ~36KB via a smaller deployment.

The price per byte of state is unchanged from the current protocol (200 gas per byte at the base fee, whether paid as gas or value), so the cost of state growth scales with the amount written. At a base fee of 100 gwei and $0.02/MON, a block writing the maximum ~1.87MB under this MIP costs approximately 37.5 MON (~$0.75): 15 MON in gas and 22.5 MON in value deposits. Sustaining this rate for a day (~216,000 blocks at 400ms) would write ~405GB of state at a cost of approximately $162,000, compared to ~162GB at approximately $65,000 under the current protocol.

### Deposit Price

The deposit cost is priced at the block’s base fee to maintain consistency between the gas-charged and value-charged portions.

Under the current protocol, each byte of deployed code costs 200 gas, paid at the transaction’s effective gas price. Of this price, the base fee is burned and the priority fee is paid to the block proposer for inclusion in the block. The value-paid portion of the deposit consumes no block gas, so there is no inclusion for a priority fee to pay for; charging `(CODE_DEPOSIT_COST - PARTIAL_CODE_DEPOSIT_COST) * block.basefee` per byte therefore reproduces exactly the burned portion of the current price. The total burned per byte of code is the same whether it is paid as gas or as value, and the deployer cannot reduce or inflate the deposit by choosing a priority fee.

Pricing at `block.basefee` means the deposit is only known once the block is built. Deployers should set `max_deposit_value` with headroom for base fee movement; only the deposit computed at the block’s base fee is charged.

### Maximum Initcode Size

The value of `MAX_DEPLOY_INITCODE_SIZE` is set conservatively to fit below the current encoded size limit in the reference consensus client’s transaction pool of 384KiB. This choice departs from the established pattern in Ethereum and Monad of `2 * MAX_DEPLOY_CODE_SIZE`, but permits standard constructor patterns without requiring analysis and potential changes to the networking layer of the protocol.

Enforcement of this limit at the execution layer means that the feature does not implicitly depend on the current behaviour at the transport layer, and means that contracts cannot construct arbitrarily-large initcode built in memory.

### Single Transaction

Early versions of this proposal suggested multi-transaction deployment mechanisms where partial contract chunks could be uploaded separately and combined with an explicit finalization step. This MIP avoids this direction to minimise downstream changes to the database layer and complexity for users deploying contracts. Scaling beyond 256KiB is likely to require such a mechanism due to limits at the transport layer.

### Encoding

`CREATEBIG` is allocated under the `EXTENSION` mechanism defined in [MIP-7](./MIP-7.md), rather than to an unused single-byte opcode, to avoid collision with future changes to the Ethereum execution layer. Selector `0x02` is the next unallocated selector after those assigned by [MIP-18](./MIP-18.md).

`CREATEBIG` needs no immediate arguments, so it does not use the argument encodings defined in MIP-7. All of its inputs are taken from the stack, as for `CREATE2`, so that they can be computed at runtime.

## Backwards Compatibility

Under MIP-7, the extended opcode `0xAE 0x02` currently behaves like `INVALID`. Existing code that executes this sequence halts exceptionally today and will execute successfully after this MIP. Such code is not expected to exist in practice, because the sequence has never had defined behavior on Monad or Ethereum.

A trailing `EXTENSION` byte has no selector and must halt exceptionally, as MIP-7 specifies.

`JUMPDEST` analysis is unaffected.

### Compiler Support

Existing compilers targeting the EVM do not have support for `CREATEBIG` and must be updated to support it. Developers wishing to deploy a large contract using `CREATEBIG` have two options:

- Use Yul’s `verbatim_5i_1o` to insert the opcode manually as inline assembly.
- Use the deterministic factory contract specified in MRC-22.

## Test Cases

**TODO**

## Reference Implementation

This MIP is implemented on branch **TODO** of the Monad reference executable specification.

## Security Considerations

### State Growth

See [Partial Value-paid Deposit](#partial-value-paid-deposit). State growth is priced identically to the current protocol, and the partial-value design caps the per-block state growth at a manageable level relative to the current protocol. A slow-block denial of service via increased per-block state growth requires infeasibly large sums of money to sustain; the protocol is resilient to transient slow block execution.

### Reserve Balance

The escrow is a debit from the deployer’s balance, and is subject to Monad’s reserve balance handling in the same way as value transferred out of the account by `CALL`. The full `max_deposit_value` is debited while the constructor runs, and is visible to the reserve balance precompile ([MIP-4](./MIP-4.md)) during that time. When `CREATEBIG` completes, the unused portion is credited back, so that only the charged deposit remains debited. That the deposit is burned rather than credited to another account does not affect the reserve balance check, which considers only the debited account. The debit is undone if state changes containing the `CREATEBIG` are reverted.

Contract creation from delegated EOA code is not permitted, so the deployer is never an EOA. It may, however, have no code while `CREATEBIG` executes: when `CREATEBIG` is executed by initcode, the deployer is the contract under construction. Such an account is treated as an EOA by the reserve balance check while it has no code, and its reserve is determined by its balance before the transaction. An escrow or deposit charged from it can therefore cause a reserve balance violation only if the account held a balance before the transaction, for example because value was sent to its address before deployment. Under the existing reserve balance rules, the violation is cleared if construction completes with non-empty code or the account self-destructs during construction, and persists if construction completes with empty code.

An EOA that funds a deployment through a contract, such as the companion factory, transfers value as for any other call: only value that is not returned to it within the transaction counts against its reserve. Deployers should note that a reserve balance violation reverts the transaction after the constructor has run, consuming its gas.

### Tooling

Ecosystem tooling such as indexers and RPC must account for potentially large code sizes in responses. Tracers and indexers must recognize call frames created by `CREATEBIG` as contract creations, and trace formats that report a frame type (such as `CREATE` or `CREATE2`) need a type for these frames.

### Simulation

RPC simulation methods such as `eth_call` and `eth_estimateGas` commonly execute with `block.basefee` set to zero when no gas price is given, in which case `CREATEBIG` charges no deposit. Tooling that determines `max_deposit_value`, or the value to send to a contract that funds the deposit, must simulate with a realistic base fee, or compute the deposit directly as `(CODE_DEPOSIT_COST - PARTIAL_CODE_DEPOSIT_COST) * |R| * block.basefee`.

### Deposit Funding

The value-paid deposit is only charged when a contract executes `CREATEBIG` with a non-zero `max_deposit_value`, so existing contracts cannot be made to pay it. A new contract that executes caller-supplied initcode via `CREATEBIG` with a `max_deposit_value` drawn from its own balance, rather than from value supplied by its caller, allows callers to burn that balance. Such contracts should fund deposits from `msg.value`, as the companion factory does.

### Code-loading Costs

The execution of contracts larger than 128KiB is priced by MIP-20. The pricing constants in MIP-20 must be confirmed by benchmarking at code sizes up to `MAX_DEPLOY_CODE_SIZE`, so that the linear model holds over the full range of code sizes this MIP permits.

### Hard-coded Size Limits

Any code that presumes a hard-coded contract size limit of 128KiB may break, and must be updated to handle the new maximum size.

## Related Prior Art

### Code and Initcode Size Limits

[EIP-170](https://eips.ethereum.org/EIPS/eip-170) limits deployed code on Ethereum to 24,576 bytes, motivated by the cost of loading code being proportional to its size while account access is priced at a flat rate. [EIP-3860](https://eips.ethereum.org/EIPS/eip-3860) limits initcode to twice that size (49,152 bytes) and introduces a charge of 2 gas per 32-byte word of initcode to cover jumpdest analysis. Monad currently raises these limits to 128KiB and 256KiB respectively, but retains the requirement that the full code deposit is paid as gas within a single transaction; this is the constraint the present MIP relaxes.

### Larger Contracts on Ethereum

[EIP-7954](https://github.com/ethereum/EIPs/blob/f1ade090fd315895461fc3e249cb1a675aeb55a9/EIPS/eip-7954.md) raises Ethereum’s limits to 64KiB of code and 128KiB of initcode, preserving the 2:1 ratio and changing nothing else. At these sizes the code deposit still fits comfortably within a transaction’s gas limit, so no change to how the deposit is paid is required.

[EIP-7907](https://github.com/ethereum/EIPs/blob/b3a1f7ba0554f57c5d892028f42d6bc8716bfb88/EIPS/eip-7907.md) builds on EIP-7954 by metering code loading by size, so that the cost of loading large code is borne by the operations that load it. This MIP relies on MIP-20, which applies the same principle on Monad, for the execution of contracts deployed by `CREATEBIG`.

### Value-paid Deployment Fees

Arbitrum Stylus deploys WebAssembly programs in two steps: the compressed program is first stored as contract code, then activated through a call to the payable `activateProgram` method of the `ArbWasm` precompile. Activation computes a data fee that must be paid as call value; the call fails if the value sent is insufficient, and any excess is refunded to the caller. This MIP similarly charges a fee in value that is computed during deployment, but holds it in escrow from the deployer’s balance, bounded by an explicit cap, rather than requiring it as call value; the unused portion of the cap is returned by the protocol rather than by a value transfer. Unlike Stylus, where the data fee is paid to a network fee account, the deposit here is burned, and is paid in the same operation that creates the contract rather than in a separate activation step.

### Base Fee Burning

[EIP-1559](https://eips.ethereum.org/EIPS/eip-1559) burns the base fee portion of each transaction’s gas price, and [EIP-4844](https://eips.ethereum.org/EIPS/eip-4844) introduces a separate, burned blob base fee to price data outside the main gas market. The value-paid deposit in this MIP is likewise burned and priced at the block’s base fee, but does not introduce a separate fee market: the gas-paid portion of the deposit keeps code deployment subject to the existing base fee adjustment.

## Future Directions

In the future, deploying contracts larger than 256KiB may be desirable. Doing so requires an extension to the design in this MIP to account for multi-part uploads, as well as an analysis of potential changes to the database layer. An extension in this manner is likely to be more complex, and may require implementation via an enshrined precompile. This extension is out of scope for this MIP based on current application requirements for large contracts.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
