---
mip: 4
title: Reserve Balance Introspection
description: Add reserve balance precompile to query reserve balance violation state during transaction execution.
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-4-reserve-balance-introspection/363
status: Review
type: Standards Track
category: Core
created: 2026-01-08
---

## Abstract

Add a new precompile at address `0x1001` with a method `dippedIntoReserve` that returns whether the current execution state is in reserve balance violation.
This enables contracts to detect and recover from temporary reserve violations before transaction completion.

## Motivation

Monad's reserve balance mechanism (per the initial spec, Algorithm 3) reverts transactions that leave any touched account below its reserve threshold at execution end.
However, the check is performed post-execution: contracts have no way to know during execution whether they are in a violation state.

The reserve balance precompile allows contracts to query violation state mid-execution and adjust behavior accordingly—either by restoring balances, taking an alternative code path, or reverting early with a meaningful error.

## Specification

### Constants

| Name                           | Value        |
| ------------------------------ | ------------ |
| `GAS_DIPPED_INTO_RESERVE`      | `100`        |
| `SELECTOR_DIPPED_INTO_RESERVE` | `0x3a61584e` |

### Precompile

The new precompile has address `0x1001`, following the existing staking precompile at `0x1000`, and satisfies the following Solidity interface:

```solidity
interface IReserveBalance {
    function dippedIntoReserve() external returns (bool);
}
```

The Solidity selector for `dippedIntoReserve` is `SELECTOR_DIPPED_INTO_RESERVE (0x3a61584e)`.

### Gas Cost

Calling `dippedIntoReserve()` has a gas cost of `GAS_DIPPED_INTO_RESERVE (100)`, equivalent to the cost of one `tload`. 
Implementations should incrementally update their state to track violations of the reserve balance constraints, rather than iterating over the set of modified accounts in the current transaction on each call to the precompile.
Then `dippedIntoReserve()` should be a check of this violation state and therefore should have similar resource usage to a load from transient storage.

This was not benchmarked, but aligns with benchmarking and costing for the staking precompile's gas costs, which were calculated from the number of database loads and stores, events, and transfers.
The reserve balance check produces no events or transfers and is analagous to a load from transient storage instead of database storage and thus uses the cost for a `tload`.

### Semantics

The method `dippedIntoReserve()` evaluates the condition that `DippedIntoReserve` (Algorithm 3 of the initial spec) would return, substituting the current state for the post-execution state.
The check considers all accounts touched in the transaction, regardless of call depth.

The return value is ABI-encoded as a Solidity `bool`—i.e., a 32-byte word in returndata, consistent with standard Solidity ABI encoding.
This means callers can invoke the precompile via a normal contract call and decode the result using standard ABI decoding.

Calldata must consist of exactly the 4-byte `SELECTOR_DIPPED_INTO_RESERVE`.
Any other calldata is invalid: if the selector does not match `dippedIntoReserve()` (i.e. the selector is unrecognized) the contract must revert with the error message "method not supported".
If extra calldata is appended beyond the selector, the precompile must revert with the error message "input is invalid".

The method `dippedIntoReserve()` is not payable and must revert with the error message "value is nonzero" when called with a nonzero value.

The precompile must be invoked via `CALL`.
Invocations via `STATICCALL`, `DELEGATECALL`, or `CALLCODE` must revert.
Invocations via [EIP-7702](https://eips.ethereum.org/EIPS/eip-7702) delegations targeting the precompile address must revert.

Reverts consume all gas provided to the call frame.
This is consistent with the behavior of Ethereum precompiles, which do not return remaining gas on failure, as opposed to Solidity functions which return unused gas on revert.

In case more than one revert condition is present, the revert error message must correspond with the conditions evaluated in the following order:

1. is not invoked via `CALL`
2. `gas < GAS_DIPPED_INTO_RESERVE`
3. `len(calldata) < 4`
4. `calldata[:4] != SELECTOR_DIPPED_INTO_RESERVE`
5. `value > 0`
6. `len(calldata) > 4`

## Rationale

A previous design proposed adding a new opcode with similar semantics.
Since this introspection feature is intended for direct use by smart contract developers (e.g., in bundler entrypoint contracts), a precompile was chosen because it can be called immediately without requiring compiler or toolchain updates.

The semantics described above (strict calldata validation, ABI-encoded return values, rejecting calls with value, conventions around `*CALL` opcodes & EIP-7702, revert messages, and all-gas-consuming reverts) are chosen for explicit consistency with the existing Monad staking precompile.

## Backwards Compatibility

This proposal adds a new precompile and does not modify existing behavior.
Contracts that do not use the precompile are unaffected.

## Security Considerations

The precompile is read-only and exposes information that is already implicitly available (the transaction will revert if violation persists).
No new attack surface is introduced.

## References

- [Monad Initial Specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
