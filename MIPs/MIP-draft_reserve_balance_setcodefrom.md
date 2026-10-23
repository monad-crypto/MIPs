---
title: Reserve Balance-Compatible SETCODEFROM Opcode
description: Activate EIP-8298 with reserve balance rules for accounts that adopt code while delegated.
author: Piotr Dobaczewski (@pdobacz)
discussions-to: <URL>
status: Draft
type: Standards Track
category: Core
created: 2026-10-09
requires: 4
---

## Abstract

This MIP makes the `SETCODEFROM` opcode from [EIP-8298] work under Monad's reserve balance rules.

`SETCODEFROM` follows the [EIP-8298] spec, but an account that adopts regular code while delegated stays under the reserve balance check for the migrating transaction and the rest of a `k`-block window; in-flight transactions of such an account that execute after the adoption are included, fail, and pay full gas.

## Motivation

[EIP-8298] has two motivating goals: code reuse for created and existing contracts and EOA migration. While the code reuse scenario does not interfere with Monad's rules (contracts are exempt from current reserve balance checks), the EOA migration one does. An EOA which migrates to an account with regular code would fall under the contract exemption of current reserve balance checks and allow its balance to be drained, while consensus still admits in-flight transactions for `k=3` blocks.

By making amendments to the reserve balance checks on top of [EIP-8298] logic, this proposal makes the full functionality of `SETCODEFROM` compatible with Monad.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

This MIP affects both the execution daemon and the consensus daemon.

### Parameters

| Name                                 | Value      |
| ------------------------------------ | ---------- |
| `RESERVE_BALANCE_DELAY_BLOCKS` (`k`) | `3` blocks |

### Opcode

This proposal assumes [EIP-8298] semantics of `SETCODEFROM` (`0xA7`) are adopted unchanged, except the following sections, which do not apply on Monad:

- **Block-Level Access Lists**: EIP-7928 is not adopted ([MIP-15](./MIP-15.md))
- **Public Mempool**: non-consensus rules for EIP-8141 frame transactions, which Monad does not have
- **Gas Costs**: priced against EIP-8037 and EIP-8038, neither of which takes effect on Monad (MIP-15)

(**EDITORIAL NOTE**: the above assumption would be better off in a separate MIP documenting the way EIP-8298 is adopted on Monad)

Monad's restriction of `CREATE` and `CREATE2` in the context of a delegated account applies to a frame if the current account held a delegation indicator when the frame started. A `SETCODEFROM` in the frame does not lift the restriction for the rest of the frame, because under [EIP-8298] the frame continues running the code it loaded, which for a frame entered through a delegation indicator is delegated code. `CREATE` becomes available to the account in frames that start after the adoption, including child frames of the adopting frame that run in the account's context.

### Reserve Balance Check

The check runs at the end of every transaction for every account the transaction touched. The transaction reverts if `dipped_into_reserve` is true for any account. `below_threshold` is the threshold comparison as specified today and is not changed by this MIP.

Current behaviour:

```python
def dipped_into_reserve(tx, account):
    if account == STAKING_CONTRACT:
        return False
    code = code_now(account)
    if is_regular_code(code):
        return False
    delegated = is_delegation_indicator(code)
    if code == b"" and selfdestructed(account):
        return False
    if account == tx.sender and may_empty(account, delegated):
        return False
    return below_threshold(tx, account)


def may_empty(account, delegated):
    return (
        not delegated
        and not sent_in_window(account, RESERVE_BALANCE_DELAY_BLOCKS)
        and not authority_in_window(account, RESERVE_BALANCE_DELAY_BLOCKS)
    )
```

Proposed behaviour:

```python
def dipped_into_reserve(tx, account):
    if may_empty(account):
        return False
    return below_threshold(tx, account)


def may_empty(account):
    return (
        not delegated_in_lagged_state(account, RESERVE_BALANCE_DELAY_BLOCKS)
        and not sent_in_window(account, RESERVE_BALANCE_DELAY_BLOCKS)
        and not authority_in_window(account, RESERVE_BALANCE_DELAY_BLOCKS)
    )
```

`sent_in_window` and `authority_in_window` are as today: the sender of every transaction in the window, and every recovered authority of an authorization in the window, whether or not the authorization applied. `sent_in_window` covers the transactions before the current one. `authority_in_window` also covers the authorization list of the current transaction.

The window MUST cover exactly the blocks after the lagged state read by `delegated_in_lagged_state`: the previous `RESERVE_BALANCE_DELAY_BLOCKS - 1` blocks and the current block up to the current transaction.

`delegated_in_lagged_state` reads the account's code in the state consensus validates the current block against.

```python
def delegated_in_lagged_state(account, RESERVE_BALANCE_DELAY_BLOCKS):
    lagged = state_at_end_of_block(block.number - RESERVE_BALANCE_DELAY_BLOCKS)
    return is_delegation_indicator(code(account, lagged))
```

### In-Flight Transactions of a Migrated Account

#### Consensus

Consensus MUST NOT sequence a transaction to which the [EIP-3607] sender restriction applies if its sender holds regular code in the state the block is validated against.

#### Execution

A sequenced transaction to which the [EIP-3607] sender restriction applies and whose sender holds regular code at execution MUST NOT immediately invalidate the block. Execution MUST process the transaction as an included transaction whose execution fails before any code runs. Validation and execution have the following steps:

1. Signature, chain id, gas limit and intrinsic gas are validated as today.
2. The sender's code is validated. The sender holds regular code.
3. The transaction's nonce and the sender's balance are validated as today.
4. The transaction's nonce is consumed.
5. The transaction's fees are charged.
6. The transaction's authorization list is processed.
7. No value is transferred, no code runs, no contract is created, no log is emitted and no trace frame is produced.
8. The receipt has status 0 and `gasUsed` equal to the gas limit.

### Reserve Balance Introspection

The `dippedIntoReserve()` method of the reserve balance precompile defined in [MIP-4](./MIP-4.md) MUST evaluate `dipped_into_reserve` as specified in Reserve Balance Check for every account touched so far, with the current state in place of the post-execution state.

```python
def dipped_into_reserve_precompile(tx):
    return any(dipped_into_reserve(tx, account) for account in touched_accounts(tx))
```

## Rationale

### Reading the Delegation From the Lagged State

Consensus decides whether a sender's transaction may empty the account from three facts: whether the account is delegated in the lagged state, whether it is an authority in the window, and whether it sent a transaction in the window. Execution must never let an account empty when consensus has budgeted it as unable to, so `may_empty` uses the same facts, and `delegated_in_lagged_state` is the first of them.

Before this MIP, the delegation at the start of the transaction together with `authority_in_window` gave the same answer, because an account delegated in the lagged state could stop being delegated only through an authorization in the window. `SETCODEFROM` adds a second way out that leaves no trace in block bodies. Reading the lagged state covers it: an account delegated in the lagged state stays under the check until consensus sees its new code. For every account that never adopts code, the term changes nothing, because such an account is either still delegated or an authority in the window.

This relies on adopting regular code being irreversible. `SETCODEFROM` rejects sources whose code starts with `0xEF`, so it never installs a delegation indicator. [EIP-7702] skips authorizations whose authority holds regular code. Under [EIP-6780] `SELFDESTRUCT` deletes only an account created in the same transaction, and [EIP-8298] does not count adopting code as creating the account. An account holding regular code therefore never returns to empty code or a delegation indicator, and its nonce is never reset, which would reopen replay of its earlier transactions and authorizations.

`may_empty` has no separate check of the account's current delegation. Only an authorization writes a delegation indicator, so an account delegated at the start of a transaction was either delegated in the lagged state or delegated by an authorization in the window, including the current transaction's authorization list. This holds because the window covers exactly the blocks after the lagged state.

An alternative is to record `SETCODEFROM` migrations as events. This would add execution-derived state that must survive restarts and be visible to speculatively executed transactions in the same block under Monad's parallel execution model. The lagged state is fixed for the block and is already read by consensus.

### Removing the Staking Contract Carve-Out

The staking contract is never a sender or an authority, and never delegated. It therefore satisfies `may_empty` in every transaction and needs no explicit exemption.

### Coexistence With a Post-ECDSA Origination Mechanism

A mechanism called "Flexible Authentication" has also been proposed, under which an account keeps its address, replaces its ECDSA key with a configured set of authenticators and a signing policy, keeps originating transactions through a new transaction type, and applies reconfigurations after the same `k`-block delay. SETCODEFROM and such a mechanism address the same problem with different end states, and both should be usable on one account.

The reserve balance check depends on two properties of an account: whether the protocol accepts transactions from it, and whether code executing in its context can move its balance. An account with both properties is what the check calls delegated: it is always checked, never allowed to empty, and budgeted by consensus as delegated. Today only an account with a delegation indicator has both. An account that adopts regular code while keeping a configured origination mechanism has both as well, so it belongs in the same class, for as long as it holds the mechanism and visibly to consensus through state. No window is needed for it; the window in this MIP exists for an account that loses origination at adoption, which today is every account.

When such a mechanism is specified, three adaptations follow from this MIP:

- an account holding regular code that the mechanism accepts as sender never satisfies `may_empty`;
- the mechanism's transaction type is outside the in-flight rule, which applies only to [EIP-3607] restricted types;
- the authority to enable or change origination for an account with regular code is derived from that code, never from a retired authentication method, so that a retired ECDSA key cannot re-enable origination for an account that adopted code to disable it.

### In-Flight Transactions of a Migrated Account

A transaction signed by an account's key can be sequenced while the state consensus validates against still shows the account as an EOA or as delegated, and execute after the account has adopted regular code. This happens only within `RESERVE_BALANCE_DELAY_BLOCKS` of the adoption. Under [EIP-3607] such a transaction invalidates the block, which is not an option once consensus has sequenced it. Executing it would let the old key act on the account after migration. Including it without charging would give up to the reserve of block space per migration for free. Charging the full gas limit is consistent with the reserve check, which keeps the migrated account above its threshold for the same window so the fee can be paid.

### Reserve Balance Introspection

The answer of `may_empty` is fixed for the whole transaction. The lagged state is fixed for the block, and the sender and authority windows are known when the transaction starts. A `SETCODEFROM` therefore does not change the answer of `dippedIntoReserve()` within the transaction, and the answer agrees with the end-of-transaction check. An account holding regular code can now return `true`, in the transaction that adopted the code and in the following `RESERVE_BALANCE_DELAY_BLOCKS - 1` blocks, whenever its balance is below its threshold. Before this MIP only accounts with empty code or a delegation indicator could.

### Open Questions

- `delegated_in_lagged_state` requires execution to read the state at the end of block `n - RESERVE_BALANCE_DELAY_BLOCKS`. Consensus already reads that state, but execution of block `n` today reads only the state of block `n - 1`. A direct read costs one account read for every account that dips below its threshold with no sender or authority in the window. A client can instead cache the migrations of completed blocks, provided it can rebuild that cache from the lagged state after a restart.

## Backwards Compatibility

Needs discussion.

## Test Cases

TBD

## Security Considerations

Needs discussion.

### Authorization Replay Against Migrated Accounts

Any account that has signed an EIP-7702 authorization can be kept from emptying by anyone who re-includes that authorization every `RESERVE_BALANCE_DELAY_BLOCKS` blocks, because an authority in the window is treated as delegated whether or not the authorization applied. A migrated account has necessarily signed one, so it stays exposed after migration: while the replay continues its code cannot move the balance below its threshold. This is the constraint the account had while delegated and is not introduced by this MIP.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).

[EIP-3607]: https://eips.ethereum.org/EIPS/eip-3607
[EIP-6780]: https://eips.ethereum.org/EIPS/eip-6780
[EIP-7702]: https://eips.ethereum.org/EIPS/eip-7702
[EIP-8298]: https://eips.ethereum.org/EIPS/eip-8298
