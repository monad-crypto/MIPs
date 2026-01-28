---
mip: 4
title: Reserve Balance Introspection
description: Add reserve balance precompile to query reserve balance violation state during transaction execution.
author: Category Labs
category: Core
created: 2026-01-08
---

## Abstract

Add a new precompile at address `0x1001` with a method `dippedIntoReserve` that returns whether the current execution state is in reserve balance violation. This enables contracts to detect and recover from temporary reserve violations before transaction completion.

## Motivation

Monad's reserve balance mechanism (per the initial spec, Algorithm 3) reverts transactions that leave any touched account below its reserve threshold at execution end. However, the check is performed post-execution—contracts have no way to know during execution whether they are in a violation state.

The reserve balance precompile allows contracts to query violation state mid-execution and adjust behavior accordingly—either by restoring balances, taking an alternative code path, or reverting early with a meaningful error.

## Specification

### Precompile

The new precompile has address `0x1001` and satisfies the following Solidity interface:

```solidity
interface IReserveBalance {
    function dippedIntoReserve() external view returns (bool);
}
```

### Gas Cost

The gas cost of calling `dippedIntoReserve()` should be constant. Implementations should incrementally update their violation state, rather than iterating over the set of modified accounts in the current transaction on each call to the precompile.

A precise gas cost for the method is TBD pending benchmarking.

### Semantics

The method `dippedIntoReserve()` evaluates the condition that `DippedIntoReserve` (Algorithm 3 of the initial spec) would return, substituting the current state for the post-execution state.

## Rationale

A previous design proposed adding a new opcode with similar semantics. Since this introspection feature is intended for direct use by smart contract developers (e.g., in bundler entrypoint contracts), a precompile was chosen because it can be called immediately via standard `staticcall` without requiring compiler or toolchain updates.

## Backwards Compatibility

This proposal adds a new precompile and does not modify existing behavior. Contracts that do not use the precompile are unaffected.

## Security Considerations

The precompile is read-only and exposes information that is already implicitly available (the transaction will revert if violation persists). No new attack surface is introduced.

## References

- [Monad Initial Specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
