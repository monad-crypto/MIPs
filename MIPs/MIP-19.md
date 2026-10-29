---
mip: 19
title: Reserve Balance-Compatible SETCODEFROM Opcode
description: Activate EIP-8298 with reserve balance rules for accounts that adopt code while delegated.
author: Piotr Dobaczewski (@pdobacz)
discussions-to: https://forum.monad.xyz/t/mip-19-reserve-balance-compatible-setcodefrom-opcode/572
status: Draft
type: Standards Track
category: Core
created: 2026-10-28
requires: 4
---

## Abstract

This MIP makes the `SETCODEFROM` opcode from [EIP-8298] work under Monad's reserve balance rules.

`SETCODEFROM` follows the [EIP-8298] spec, except that a delegated account can adopt regular code only in a transaction it sent or with an active reserve of `0`. An account that adopts regular code in a transaction it sent stays under the reserve balance check for the adopting transaction and the rest of a `k`-block window; in-flight transactions of such an account that execute after the adoption are included, fail, and pay full gas.

## Motivation

[EIP-8298] has two motivating goals: code reuse for created and existing contracts and EOA migration. While the code reuse scenario does not interfere with Monad's rules (contracts are exempt from current reserve balance checks), the EOA migration one does. An EOA that adopts regular code would fall under the contract exemption of current reserve balance checks and allow its balance to be drained, while consensus still admits in-flight transactions for `k=3` blocks.

By amending the reserve balance check on top of [EIP-8298], this proposal makes `SETCODEFROM` serve both goals while staying compatible with Monad.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

This MIP affects both the execution daemon and the consensus daemon.

The active reserve of an account is as defined in the draft MIP "Account-configurable reserve balance". The only property of that design this MIP relies on is that the reserve can be set to zero.

(**EDITORIAL NOTE**: add that MIP to `requires` once it has a number)

### Parameters

| Name                                 | Value      |
| ------------------------------------ | ---------- |
| `RESERVE_BALANCE_DELAY_BLOCKS` (`k`) | `3` blocks |

### `SETCODEFROM` Opcode

This proposal assumes [EIP-8298] semantics of `SETCODEFROM` (`0xA7`) are adopted, except for the following sections, which do not apply on Monad:

- **Block-Level Access Lists**: EIP-7928 is not adopted ([MIP-15](./MIP-15.md))
- **Public Mempool**: non-consensus rules for EIP-8141 frame transactions, which Monad does not have
- **Gas Costs**: priced against EIP-8037 and EIP-8038, neither of which takes effect on Monad (MIP-15)

(**EDITORIAL NOTE**: the above assumption would be better off in a separate MIP documenting the way EIP-8298 is adopted on Monad)

In addition to [EIP-8298], if the current account holds a delegation indicator, `SETCODEFROM` causes an exceptional halt unless the current account is the sender of the transaction or its active reserve is `0`. The halt happens before `SETCODEFROM_SOURCE_GAS` is charged, together with the other halts of [EIP-8298]. When the current account is not the sender, the gas of `SETCODEFROM` includes the cost of reading its active reserve.

### `CREATE` and `CREATE2` Restriction on Delegated Accounts

Monad's restriction of `CREATE` and `CREATE2` in the context of a delegated account applies to a frame if the current account held a delegation indicator when the frame started. A `SETCODEFROM` in the frame does not lift the restriction for the rest of the frame, because the restriction is decided when the frame starts. `CREATE` becomes available to the account in frames that start after the adoption, including child frames of the adopting frame that run in the account's context.

### Reserve Balance Check

The check runs at the end of every transaction for every account the transaction touched. The transaction reverts if `dipped_into_reserve` is true for any account. Comments mark the lines this MIP adds or changes:

```python
def dipped_into_reserve(tx, account):
    if account == STAKING_CONTRACT:
        return False
    code = code_now(account)
    if (
        is_regular_code(code)
        and account != tx.sender                                       # new
        and not sent_in_window(account, RESERVE_BALANCE_DELAY_BLOCKS)  # new
    ):
        return False

    # An account holding regular code reaches this line only as the sender or
    # while in sent_in_window, which it can only be after adopting the code
    # while delegated in the window.
    treat_as_delegated = code != b""                                   # changed
    # Was: delegated = is_delegation_indicator(code)

    if code == b"" and selfdestructed(account):
        return False
    if account == tx.sender and may_empty(account, treat_as_delegated):
        return False
    return below_threshold(tx, account)


def may_empty(account, delegated):
    return (
        not delegated
        and not sent_in_window(account, RESERVE_BALANCE_DELAY_BLOCKS)
        and not authority_in_window(account, RESERVE_BALANCE_DELAY_BLOCKS)
    )
```

The authorities of a transaction are the addresses recovered from the authorizations in its authorization list, whether or not each authorization applies.

`below_threshold`, `may_empty`, `sent_in_window` and `authority_in_window` are unchanged in this MIP.

### In-Flight Transactions of a Migrated Account

#### Consensus

Consensus MUST NOT sequence a transaction to which the [EIP-3607] sender restriction applies if its sender holds regular code in the state the block is validated against. The transaction pool MUST NOT propose such a transaction.

#### Execution

A sequenced transaction to which the [EIP-3607] sender restriction applies and whose sender holds regular code at execution MUST NOT immediately invalidate the block. Execution MUST process the transaction as an included transaction whose execution fails before any code runs. Validation and execution have the following steps:

1. Signature, chain id, gas limit and intrinsic gas are validated as today.
2. The sender's code is checked. The sender holds regular code.
3. The transaction's nonce is not validated against the sender's nonce. A sender's nonce of `2^64 - 1` invalidates the block as specified in [EIP-2681].
4. The sender's balance is validated as today.
5. The sender's nonce is set to one above the larger of the sender's nonce and the transaction's nonce.
6. The transaction's fees are charged.
7. The transaction's authorization list is processed as specified in [EIP-7702].
8. No value is transferred, no code runs, no contract is created and no log is emitted.
9. The transaction's trace has one top-level frame, which fails with a dedicated status. For a creation transaction it is a `CREATE` frame whose address is derived from the sender and the sender's nonce before step 5.
10. The receipt has status 0 and `gasUsed` equal to the gas limit.

#### Interfaces

Every interface that reports the `contractAddress` of a creation transaction on this path, such as `eth_getTransactionReceipt` and `eth_getBlockReceipts`, MUST report the address of its top-level frame.

### Reserve Balance Introspection

The `dippedIntoReserve()` method of the reserve balance precompile defined in [MIP-4](./MIP-4.md) MUST evaluate `dipped_into_reserve` as specified in Reserve Balance Check for every account touched so far, with the current state in place of the post-execution state.

## Rationale

### Adoption by Delegated Accounts

Consensus budgets block `n` against the state at the end of block `n - k`. An account that adopted regular code while delegated in blocks `n - k + 1` to `n` is still delegated in that state. A solution must ensure that either (1) consensus admits no further transaction from such an account, or (2) the reserve balance check keeps it checked.

#### Restricting Adoption to the Sender or a Zero Reserve

An active reserve of `0` provides (1). Consensus admits no transaction from the account, so the account can have no in-flight transactions. An update to the reserve takes effect `k` blocks after the block that schedules it, so the reserve that execution reads at block `n` is the one consensus applies. Such an account stays exempt as holding regular code.

Adoption by the sender provides (2). The adopting transaction puts the account in `sent_in_window`, so the reserve balance check keeps the account checked for the window with no new state and no reads.

A self-sent migration works as in [EIP-8298]. A migration through a zero reserve is run by another account, such as a relayer or an [ERC-4337] bundler, at least `k` blocks after the account sets its reserve to `0`.

#### Alternatives

| Alternative              | Mechanism                                                                                               | Drawbacks                                                                                                                                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reading the lagged state | `may_empty` reads the account's code at the end of block `n - k`                                        | unpriced read of an otherwise unloaded state for every account with regular code below its threshold; nodes bootstrapped by statesync cannot execute the next `k - 1` blocks; witnesses and RPC need a second state |
| Sender or authority      | `SETCODEFROM` halts unless the account is the sender or an authority of the transaction                 | relayed migrations need an authorization signed by the account, a Monad-specific wallet condition; replaying any old authorization keeps a migrated account checked indefinitely                                    |
| Migration record         | `SETCODEFROM` records the adoption block in a system account; regular code is exempt outside the window | new system account and invariant; about 22000 gas per migration; unpriced read in the reserve balance check                                                                                                         |

### Coexistence With a Post-ECDSA Origination Mechanism

A mechanism called "Flexible Authentication" has also been proposed, under which an account keeps its address and keeps originating transactions after replacing its ECDSA key. `SETCODEFROM` and such a mechanism address the same problem with different end states, and both should be usable on one account.

The reserve balance check treats as delegated an account that the protocol accepts as sender and whose code can move its balance. An account that adopts regular code while keeping a configured origination mechanism is such an account for as long as it holds the mechanism, visibly to consensus through state. No window is needed for it; the window in this MIP exists for an account that loses origination at adoption, which today is every account.

When such a mechanism is specified, three adaptations follow from this MIP:

- an account holding regular code that the mechanism accepts as sender is never exempt as holding regular code and never satisfies `may_empty`;
- the mechanism's transaction type is outside the in-flight rule, which applies only to [EIP-3607] restricted types;
- the authority to enable or change origination for an account with regular code is derived from that code, never from a retired authentication method, so that a retired ECDSA key cannot re-enable origination for an account that adopted code to disable it.

### In-Flight Transactions of a Migrated Account

Consensus can sequence a transaction signed by an account's key while the state it validates against shows the account as an EOA or as delegated, and execution can run it after the account has adopted regular code. This happens only within `k` blocks of the adoption.

An in-flight transaction is included, fails before any code runs and pays its full gas limit. Under [EIP-3607] such a transaction invalidates the block, which is not an option once consensus has sequenced it. Executing it would let the old key act on the account after migration. Including it without charging would give up to the reserve of block space per migration for free. Charging the full gas limit is consistent with the reserve check, which keeps the migrated account above its threshold for the same window so the fee can be paid.

Execution records the failure as a top-level frame with a dedicated status, as it records a reserve balance violation, so every included transaction has a frame and its trace states why it failed.

### Nonces of In-Flight Transactions

Consensus raises the predicted nonce of every authority whose authorization's nonce matches the prediction, whether or not the authorization applies. Execution processes the authorizations of an in-flight transaction (step 7 of Execution), so every authorization that applies under [EIP-7702] raises the authority's nonce as consensus predicts. If execution skipped them, such an authority would keep its old nonce, and its next transaction would carry a nonce execution does not expect and invalidate the block.

After the adoption the sender's nonce in execution moves away from the one consensus predicts. `CREATE` and `CREATE2` run by the account's new code raise it. An authorization naming the account is skipped as in [EIP-7702], so a migrated account cannot be delegated again, while consensus still raises the predicted nonce for `k` blocks. Validating the transaction's nonce against the sender's nonce (step 3 of Execution) would therefore invalidate blocks consensus has already sequenced. Consensus accepts the transaction only with the nonce it predicts and sequences each nonce once, so no transaction is executed twice.

Setting the sender's nonce to one above the larger of its nonce and the transaction's nonce (step 5 of Execution) keeps it increasing, so it never takes a value it held before, and keeps it above every nonce consensus has sequenced for the account. A later `CREATE` therefore never derives the address of a contract the account already created, nor the address derived from the nonce of a transaction consensus has sequenced.

### Contract Address of In-Flight Creation Transactions

Interfaces report the receipt's `contractAddress` of a creation transaction as the address derived from the sender and the transaction's nonce, whatever the transaction's status. On the in-flight path that address can hold a contract the account's code created, because the account's nonce in execution moves away from the transaction's nonce (see Nonces of In-Flight Transactions). Explorers, contract verification services and deployment tools would then attribute a live contract to a failed transaction.

The frame of an in-flight creation transaction derives its address from the sender's nonce in execution, and interfaces report that address. Every earlier `CREATE` by the account used a lower nonce and step 5 consumes this one, so the address never holds a contract, as for a failed creation on Ethereum. A tool that derives the address from the transaction's nonce by itself still reports the address the transaction's nonce gives.

The alternatives below, rejected for the reasons given, address the same issue at the protocol level:

| Alternative                        | Mechanism                                                                                                                     | Drawbacks                                                                                                                     |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Restricting `CREATE` in the window | the `CREATE` restriction covers a migrated account for the window; the in-flight path raises the nonce past the transaction's | breaks migration code that deploys contracts during or shortly after the migration                                            |
| Raising the nonce at adoption      | self-sent adoption raises the nonce by an offset, such as `2^24`, beyond any in-flight nonce                                  | nonce side effect absent from [EIP-8298]; nonce stops counting transactions; couples the nonce to the block gas limit and `k` |
| Delaying creation transactions     | consensus delays a delegated sender's creation transaction after another transaction in the window                            | regression for every delegated sender, unrelated to `SETCODEFROM`, hindering usage patterns in use on live EVM networks       |
| Marking in-flight transactions     | a system log marks in-flight transactions, and interfaces report no `contractAddress` for them                                | bespoke mechanism for a single field of a single interface                                                                    |
| Declaring self-sent adoption       | an access-list marker declares the adoption, and consensus sequences nothing more from the sender in the window               | bespoke condition for wallets                                                                                                 |
| Exhausting the budget              | a self-sent adoption's fee must cover the active reserve, exhausting the consensus budget                                     | fee must equal the reserve exactly, a bespoke condition for wallets                                                           |

### Reserve Balance Introspection

The answer of `may_empty` is fixed for the whole transaction. The sender and authority windows are known when the transaction starts. `SETCODEFROM` only replaces a delegation indicator with regular code, and `treat_as_delegated` is true for both. A sender that adopts regular code stays checked, and an account that adopts it with an active reserve of `0` has a threshold of `0` before the adoption. A `SETCODEFROM` in an account holding a delegation indicator therefore does not change the answer of `dippedIntoReserve()` within the transaction, and the answer agrees with the end-of-transaction check. `dippedIntoReserve()` can now return `true` for an account holding regular code, in the transaction it sent to adopt the code and while it is in `sent_in_window`, whenever its balance is below its threshold. Before this MIP only accounts with empty code or a delegation indicator could.

## Backwards Compatibility

Needs discussion.

## Test Cases

TBD

## Security Considerations

Needs discussion.

### In-Flight Transactions From a Compromised Key

In case the account's key becomes compromised at the moment of code adoption, a malicious leader with the key can fill the window with in-flight transactions from the account, each charged in full, and sweep the priority fees. An alternative design charges only the base fee on the in-flight path, so that no priority fee reaches the leader.

## Open Questions

### Compatibility With MCP and Cadence

The design of this MIP is currently incompatible with MCP and the Cadence consensus architecture. As the design of MCP and Cadence crystallizes, another MIP will specify a revised design, likely built on similar mechanisms.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).

[EIP-2681]: https://eips.ethereum.org/EIPS/eip-2681
[EIP-3607]: https://eips.ethereum.org/EIPS/eip-3607
[EIP-7702]: https://eips.ethereum.org/EIPS/eip-7702
[EIP-8298]: https://eips.ethereum.org/EIPS/eip-8298
[ERC-4337]: https://eips.ethereum.org/EIPS/eip-4337
