---
mip: 4
title: Reserve Balance Introspection
description: Add CHECKRESERVEBALANCE opcode to query reserve balance violation state during transaction execution.
author: Category Labs
category: Core
created: 2026-01-08
---

## Abstract

Add a new opcode `CHECKRESERVEBALANCE` (`0xD0`) that returns whether the current execution state is in reserve balance violation. This enables contracts to detect and recover from temporary reserve violations before transaction completion.

## Motivation

Monad's reserve balance mechanism (per the initial spec, Algorithm 3) reverts transactions that leave any touched account below its reserve threshold at execution end. However, the check is performed post-execution—contracts have no way to know during execution whether they are in a violation state.

`CHECKRESERVEBALANCE` allows contracts to query violation state mid-execution and adjust behavior accordingly—either by restoring balances, taking an alternative code path, or reverting early with a meaningful error.

## Specification

### Opcode

| Mnemonic | Opcode | Stack In | Stack Out | Description |
|----------|--------|----------|-----------|-------------|
| `CHECKRESERVEBALANCE` | `0xD0` | 0 | 1 | Push 1 if execution state is in reserve violation, 0 otherwise |

### Gas Cost

TBD pending benchmarking. Expected to be `O(N)` in the number of warm accounts (i.e., accounts with modified balances).

### Semantics

The opcode evaluates the condition that `DippedIntoReserve` (Algorithm 3 of the initial spec) would return, substituting the current state for the post-execution state.

## Backwards Compatibility

This proposal adds a new opcode and does not modify existing behavior. Contracts that do not use the opcode are unaffected.

## Security Considerations

The opcode is read-only and exposes information that is already implicitly available (the transaction will revert if violation persists). No new attack surface is introduced.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
