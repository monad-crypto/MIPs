---
mip: 18
title: Call Stack Opcodes
description: Add extension opcodes to inspect the depth and caller chain of the current call stack
author: Category Labs
discussions-to: TBD
status: Draft
type: Standards Track
category: Core
created: 2026-09-24
requires: 7
---

## Abstract

This MIP allocates two extension opcodes under the `EXTENSION` (`0xAE`) mechanism defined in [MIP-7](./MIP-7.md). `CALLSTACKDEPTH` pushes the depth of the current call frame in the EVM call stack. `CALLERN` generalizes `CALLER`: it pops an index `n` and pushes the caller address `n` frames above the current frame. Both opcodes take no immediate arguments and have constant-time implementations.

## Motivation

These opcodes are intended to support future Monad protocol upgrades under development at Category Labs.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Parameters

| Name                      | Value  |
| ------------------------- | ------ |
| `CALLSTACKDEPTH_SELECTOR` | `0x00` |
| `CALLERN_SELECTOR`        | `0x01` |
| `G_CALLSTACKDEPTH`        | 2      |
| `G_CALLERN`               | 2      |

### Extension Selectors

| Extended Opcode | Mnemonic         | Immediates | Stack Input | Stack Output |
| --------------- | ---------------- | ---------- | ----------- | ------------ |
| `0xAE 0x00`     | `CALLSTACKDEPTH` | None       | —           | `depth`      |
| `0xAE 0x01`     | `CALLERN`        | None       | `n`         | `caller`     |

Neither extended opcode is followed by argument bytes. The byte following the selector is decoded as the next instruction.

### Call Frames

A **call frame** is created for each message executed by the EVM: the top-level message of a transaction, and each message created by `CALL`, `CALLCODE`, `DELEGATECALL`, `STATICCALL`, `CREATE` and `CREATE2`. Calls to precompiled contracts create a frame for the purpose of depth accounting, but no code in that frame can observe it.

Let the frames active during execution be `F_0, F_1, ..., F_d`, where `F_0` is the frame of the transaction's top-level message and `F_d` is the currently executing frame. `d` is the **depth** of the current frame.

Let `sender(F_i)` be the value that `CALLER` returns when executed in frame `F_i`. In particular, `sender(F_0)` is the transaction origin, and for a frame created by `DELEGATECALL` or `CALLCODE`, `sender(F_i)` follows the existing semantics of `CALLER` in those frames.

### Opcode Semantics

#### `CALLSTACKDEPTH`

`CALLSTACKDEPTH` pushes `d` onto the stack.

#### `CALLERN`

`CALLERN` pops a 256-bit unsigned integer `n` from the stack, then:

- If `n <= d`, it pushes `sender(F_{d - n})` onto the stack, zero-extended to 32 bytes.
- Otherwise, it pushes `0` onto the stack.

As a result:

- `CALLERN(0)` is equivalent to `CALLER`.
- `CALLERN(CALLSTACKDEPTH)` is equivalent to `ORIGIN`.

### Gas Costs

`CALLSTACKDEPTH` costs `G_CALLSTACKDEPTH` gas. `CALLERN` costs `G_CALLERN` gas, regardless of the value of `n`. These costs apply to the complete extended opcode; no additional gas is charged for the `EXTENSION` prefix.

### Exceptional Conditions

Both opcodes are subject to the standard exceptional halting conditions for stack underflow, stack overflow and insufficient gas. `CALLERN` MUST NOT halt exceptionally because `n` is out of range.

## Rationale

### Frame Indexing

`CALLERN` is indexed so that `CALLERN(0)` coincides with `CALLER`, which makes the new opcode a strict generalization of the existing one. `CALLSTACKDEPTH` is 0-based, so that `CALLERN(CALLSTACKDEPTH)` coincides with `ORIGIN`, and no index is wasted.

### Out-of-Range Indices

An index above the current depth returns `0` rather than halting, following the precedent of `BLOCKHASH` for out-of-range lookups. This lets contracts probe the call stack without first reading its depth.

### Delegated Frames

`CALLERN` reports the same value that `CALLER` would report in each ancestor frame. As a result, `DELEGATECALL` and `CALLCODE` frames can cause the same address to appear at consecutive indices. This definition is the simplest one to specify and implement, and it ensures that every value returned by `CALLERN` was also observable by `CALLER` in some ancestor frame.

### Gas Costs

Both opcodes read state that an implementation already holds in memory for the duration of the transaction, and they can be implemented in constant time. Their cost therefore matches `CALLER` and `ADDRESS`.

### Encoding

Neither opcode needs immediate arguments, so neither uses the argument encodings defined in MIP-7. `CALLERN` takes its index from the stack instead of an immediate so that it can be computed at runtime (for example, from `CALLSTACKDEPTH`).

## Backwards Compatibility

Under MIP-7, the extended opcodes `0xAE 0x00` and `0xAE 0x01` currently behave like `INVALID`. Existing code that executes either sequence halts exceptionally today and will execute successfully after this MIP. Such code is not expected to exist in practice, because the sequences have never had defined behavior on Monad or Ethereum.

`JUMPDEST` analysis is unaffected.

## Security Considerations

### Authorization

`CALLERN` makes the identity of every ancestor caller available to a contract, not just its immediate caller. Using `CALLERN` for authorization inherits the weaknesses of authorizing with `ORIGIN`: an attacker who persuades a privileged account to call an attacker-controlled contract can relay calls that appear to originate from that account. Contracts SHOULD NOT use `CALLERN(n)` for `n > 0` for authorization.

### Context-Dependent Behavior

Both opcodes let a contract behave differently depending on how it was reached. Tools that assume a contract's behavior depends only on its immediate caller, calldata and state, such as transaction simulation, account abstraction validation and static analysis, may need to account for this.

### Call Depth

`CALLSTACKDEPTH` exposes information that was previously only observable indirectly, by approaching the call depth limit. The 63/64 gas forwarding rule already makes the depth limit unreachable in practice, so this is not expected to create new griefing vectors.

## References

- [MIP-7: Extension Opcodes](./MIP-7.md)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
