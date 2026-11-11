---
title: Account-configurable reserve balance
description: Allow accounts to configure their reserve balance through an onchain precompile
author: QEDK (@qedk)
discussions-to:
status: Draft
type: Standards Track
category: Core
created: 2026-09-29
requires: 4, 8
---

## Abstract

Introduce account-configurable reserve balances by extending the reserve balance precompile at `0x1001`. Accounts MAY select any `uint256` amount, denominated in wei. Accounts that do not configure a reserve retain the existing global default of 10 MON.

Configuration changes activate after the consensus-execution delay. Consensus accounts for scheduled reductions without treating scheduled increases as immediately available gas collateral. Existing emptying transaction eligibility and transaction-end reserve balance enforcement are otherwise preserved.

## Motivation

A single reserve cap does not accommodate every account’s transaction pattern. Frequent senders may prefer a smaller protected balance rather than waiting to become eligible for an emptying transaction. Accounts submitting many transactions may instead prefer a larger reserve to support a larger outstanding gas budget.

EIP-7702 delegated accounts also need control over the balance protected against transfers initiated through their delegated code. In particular, a sponsored transaction should be able to transfer the account’s native balance without requiring that account to maintain the default reserve indefinitely.

The existing restriction concerns the balance at transaction completion, not every intermediate balance. Temporarily entering the reserve and restoring the required balance before the final check is already permitted. This proposal only proposes making the threshold configurable.

Configuration must not allow an execution-time withdrawal to invalidate gas-payment assumptions for transactions already accepted by consensus. Consequently, a reserve reduction cannot take effect immediately within the transaction requesting it.

## Specification

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “NOT RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in RFC 2119 and RFC 8174 when, and only when, they appear in all capitals.

### Parameters

| Parameter | Value |
| --- | --- |
| `RESERVE_PRECOMPILE` | `0x0000000000000000000000000000000000001001` |
| `DEFAULT_RESERVE` | `10**19` wei, equivalent to 10 MON |
| `K` | `3`, the protocol’s consensus-execution delay, in blocks |
| `GET_K_SELECTOR` | `0xee39e7a0` |
| `GET_RESERVE_BALANCE_SELECTOR` | `0x15226b54` |
| `SET_RESERVE_BALANCE_SELECTOR` | `0x0cbbb4f6` |
| `GAS_GET_K` | `100` |
| `GAS_GET_RESERVE_BALANCE` | `25_000` |
| `GAS_SET_RESERVE_BALANCE` | `150_000` |

The three new gas charges are proposed draft parameters and require benchmarking.

The activation fork is specified separately. This MIP does not change `K`. Any future change to `K` MUST separately specify the treatment of outstanding reserve updates.

### Account configuration

Each address has a settled reserve and at most one pending update, consisting of a reserve value and an activation block (referred to as `validFrom`). An unconfigured address has a settled reserve of `DEFAULT_RESERVE` and no pending update.

Every value in `[0, 2**256 - 1]` is valid. Zero MUST NOT mean “unconfigured”. The configured value MAY exceed the account’s balance. Configuration neither transfers nor escrows MON.

For a record $r$ and block number $n$, define:

$$
\operatorname{active}(r,n)=
\begin{cases}\text{DEFAULT\_RESERVE}, & r.\text{validFrom}=0\\r.\text{settledReserve}, & 0<r.\text{validFrom}\ \text{and}\ n<r.\text{validFrom}\\
r.\text{pendingReserve},
& 0<r.\text{validFrom}\le n
\end{cases}
$$

Activation occurs logically before the first transaction of the `validFrom` block, including when that block is empty. Reading a record MUST NOT mutate storage.

### Precompile interface

Extend MIP-4 with:

```solidity
interface IReserveBalance {
    function dippedIntoReserve() external returns (bool);
    
    function getK() external returns (uint256);

    function getReserveBalance(address account)
        external
        returns (
            uint256 activeReserve,
            uint256 pendingReserve,
            uint256 validFrom
        );

    function setReserveBalance(uint256 reserve)
        external
        returns (uint256 validFrom);
}
```

Selectors are the first four bytes of the Keccak-256 hash of each canonical function signature. The existing `dippedIntoReserve()` selector remains `0x3a61584e`.

The new methods are non-payable and MUST be invoked through ordinary `CALL` semantics only. `STATICCALL`, `DELEGATECALL`, `CALLCODE`, and calls in a static execution context MUST fail. A top-level transaction to `0x1001` counts as a `CALL` with the sender as caller.

If an account’s EIP-7702 delegation designator points to the precompile, a call to that account executes empty code as specified by EIP-7702. The precompile MUST NOT be executed, and no record is read or changed.

A call whose calldata is not canonically ABI-encoded MUST fail. In particular, `getReserveBalance` MUST fail if the upper 12 bytes of its address word are nonzero.

The getters are intentionally not declared `view`.

| Method | Exact calldata length | Successful return length |
| --- | --- | --- |
| `getK()` | 4 bytes | 32 bytes |
| `getReserveBalance(address)` | 36 bytes | 96 bytes |
| `setReserveBalance(uint256)` | 36 bytes | 32 bytes |

`getK()` MUST return the protocol parameter `K` applicable to the current execution block, ABI-encoded as a `uint256`.

For recognized new selectors, validate call context, available native-call gas, zero call value, calldata encoding, and method-specific conditions, in that order. A failure detected by a recognized new method MUST leave no configuration changes, consume all gas forwarded to the precompile frame, and return empty failure data. Existing-selector and unsupported-selector behavior remains as specified in MIP-4.

The fixed native charge includes the method’s record reads, writes, and storage-growth gas costs. No additional `SLOAD`, `SSTORE`, or per-slot growth gas is charged for those operations. Actual state changes still participate in state accounting and rollback.

### Reading a configuration

`getReserveBalance(account)` MUST return the reserve active at the current execution block. If an update has not matured, it MUST also return that update’s value and `validFrom`. Otherwise, it MUST return `(activeReserve, activeReserve, 0)`.

Any caller MAY query any address. The returned reserve is a configuration threshold, not the account’s balance, currently spendable balance, or remaining consensus gas budget.

### Updating a configuration

`setReserveBalance(reserve)` MUST modify only the immediate caller’s record. It MUST NOT select the account using `tx.origin`, a delegated implementation address, or an address supplied in calldata.

When delegated account `A` executes a `CALL` to the precompile, the configuration belongs to `A`, including when a different account pays for the enclosing transaction. When an ordinary helper contract calls the precompile, it changes its own configuration, not its caller’s.

A successful setter in block `b` MUST schedule activation at `b + K`:

1. If there is no unactivated update, retain the currently active value as the settled reserve and create the pending update.
2. If an unactivated update was created earlier in the same block, replace its pending value without changing its `validFrom`.
3. If an unactivated update was created in a prior block, fail without changing the record.

Block-number addition MUST be checked for overflow. Multiple surviving updates in one block therefore use the last value in execution order. A later block cannot cancel, replace, or postpone an unactivated update. After activation, another update MAY be scheduled.

Setting `DEFAULT_RESERVE` restores the default threshold after the same delay. Setting an already active value still follows these scheduling rules.

All writes MUST participate in ordinary EVM call-frame journaling. Reverting a call frame, the enclosing transaction, or the final reserve check MUST discard the corresponding writes. Earlier successful transactions in the block remain unaffected. This does not change the separate rollback rules for EIP-7702 authorization processing.

### Persistent storage

Configuration records MUST be stored in the precompile account’s storage. At fork activation, the precompile account’s nonce MUST be set to one if it is zero, and otherwise preserved. Its balance and code MUST be preserved. No per-account records are initialized. This keeps the stateful precompile account from being treated as empty.

For account address `addr`, let slot `s`:

```solidity
s = uint256(keccak256(abi.encode(addr, uint256(0)))) & ~(uint256(0x7f))
```

This is similar to storing an address-keyed mapping in the first storage slot of a contract but we additionally mask the lower 7 bits to get a page-aligned slot allowing us to get all record values within a single page read.

The record occupies these slots:

| Slot | Encoding |
| --- | --- |
| `s` | `settledReserve`, stored in wei units |
| `s + 1` | `pendingReserve`, stored in wei units |
| `s + 2` | `validFrom`; zero indicates an unconfigured record |

An unconfigured record MUST contain zero in all three slots. A stored `validFrom` of zero indicates that the account has not been configured, and its effective reserve is `DEFAULT_RESERVE`.

A successful setter call MUST store a nonzero `validFrom`. Activation MUST NOT clear the record. The stored `validFrom` and `pendingReserve` MUST be retained until a subsequent successful setter call replaces them.

A pending update exists only when the stored `validFrom` is greater than the current block number.

### Consensus accounting

For validation of block `n`, let `h = n - K` and let $S_h$ be the protocol-designated execution state after block `h`. Consensus MUST use this snapshot, even if a validator has executed newer blocks.

Let $R_h(a,b)$ be account $a$’s reserve for block $b$ calculated using only its configuration and scheduled updates recorded in $S_h$. Updates not recorded in $S_h$ MUST NOT be considered.

Initialize the account’s remaining gas budget $G$:

$$
G_a = \min\!\left(\operatorname{balance}(S_h,a),\; R_h(a,h)\right)
$$

Process blocks $h+1,\ldots,n$ in order. Before processing transactions in each block $b$, cap the remaining budget at that block’s reserve:

$$
G_a = \min\!\left(G_a,\; R_h(a,b)\right)
$$

This cap MUST apply at each block boundary, including empty blocks. Implementations MAY apply it lazily when the account is accessed, provided the result is identical.

For a transaction not eligible for emptying, require its existing protocol gas-fee bound `F(tx)` to be no greater than $G_{sender}$, then subtract that bound. An insufficient budget makes the candidate inadmissible. Existing nonce, authorization, and other transaction-validity checks remain applicable.

For an emptying-eligible transaction, preserve the existing eligibility test and debit calculation: require its gas-fee bound to fit the sender’s snapshot balance, then set the remaining budget to the smaller of $R_h(sender, b)$ and the snapshot balance after the existing conservative emptying debit. That debit includes gas, transaction value, and any separately accounted sender charge required by the active protocol.

A scheduled reduction MUST clamp the remaining budget. A scheduled increase MUST NOT **by itself** replenish it. In particular, consensus MUST NOT initialize the window’s budget directly from an increased reserve that is scheduled to activate later in that window.

Under these rules, an update submitted in block `b` changes execution’s threshold at `b + K`. An increase becomes the ordinary reserve-budget initialization value when a snapshot at or after `b + K` is used, ordinarily at `b + 2K`. Emptying transactions remain governed by their existing exception.

### Execution accounting

Replace the global reserve cap in the existing execution checks with the account’s active reserve for the execution block. The set of protected account types and existing exemptions are unchanged: recording a configuration for an ordinary contract does not make that contract subject to the EOA reserve restriction.

Let $B_{pre}(a)$ be the account’s balance at the existing pre-transaction checkpoint, before the sender’s gas debit, and let $B_{post}(a)$ be its balance at the existing final reserve-check checkpoint. For a protected account $a$ with record $r_a$, in execution block $b$, define:

$$
\operatorname{protected}(a) = \min\!\left(B_{pre}(a),\; \operatorname{active}(r_a, b)\right)
$$

A reserve violation is determined per protected account, in exactly one of three cases:

1. **Sender eligible for emptying.** The sender is exempt from this check, as under the existing emptying exception.
2. **Sender not eligible for emptying.** A reserve violation exists if $F(tx) > \operatorname{protected}(a)$, or if $B_{post}(a) < \operatorname{protected}(a) - F(tx)$. Implementations MUST NOT replace the first condition with a zero threshold by saturating the subtraction.
3. **Any other protected account.** A reserve violation exists if $B_{post}(a) < \operatorname{protected}(a)$.

For a transaction accepted by consensus, the first condition of case 2 cannot occur, because its gas-fee bound was checked against a budget that never exceeds $\operatorname{protected}(a)$. The condition is specified so that the check is defined for every transaction.

A setter call MUST NOT change the threshold for its transaction or for later transactions in the same block. Intermediate dips remain permissible if the final check succeeds.

`dippedIntoReserve()` MUST use these same active thresholds across the transaction’s touched accounts. Its ABI, 100-gas native charge, and failure conventions remain unchanged. A newly scheduled reduction does not turn an existing reserve violation into a non-violation.

Two properties bound the record reads that the final check and `dippedIntoReserve()` require:

- **Thresholds are constant within a block.** A setter call in block $b$ keeps the settled reserve equal to the active value and sets `validFrom` greater than $b$, so $\operatorname{active}(r_a, b)$ is unaffected by any setter call executed in block $b$. Implementations MAY read each record once per block and cache the threshold.
- **Reads for accounts in case 3 can be lazy.** Such an account can only be in violation if its balance is below $B_{pre}(a)$. Implementations MAY skip reading its record while its balance is at least $B_{pre}(a)$.

## Rationale

### Extend the existing precompile

The existing address already exposes reserve balance introspection. Extending it keeps configuration and introspection together without introducing a transaction type, OPCODE or separate address.

### Delayed updates and conservative increases

Consensus cannot safely depend on the eventual success of an arbitrary internal call. Delaying activation ensures that, when a change first affects execution, the block that scheduled it is available in the corresponding consensus snapshot.

Delay alone is insufficient for increases. For example, a delegated account could schedule an increase from 10 to 100 MON, spend down to 10 MON while the old threshold still applies, and otherwise appear to offer 100 MON of gas coverage when the increase activates. Budget initialization from the snapshot’s active threshold, followed only by clamps and debits, avoids granting an unprotected budget.

The restriction on replacing a prior block’s unactivated update makes its activation deterministic from the snapshot. Allowing same-block replacement supports batching without requiring an unbounded update queue.

### Full-range configuration

Zero supports accounts intended to operate exclusively through sponsorship. A reserve above 10 MON supports larger outstanding fee commitments, subject to available balance. A value above the current balance is harmless as a cap because balance protection and budget initialization use the smaller amount.

## Backwards Compatibility

This is a consensus-changing upgrade and requires coordinated activation. Unupgraded validators will not implement the new methods or reserve-accounting rules.

Accounts that never configure a reserve retain the default behavior without migration. Existing emptying rules, ordinary-contract exemptions, and the introspection ABI are preserved.

The new selectors previously failed and become supported. Applications that assume every account permanently uses a 10 MON reserve must instead query configuration.

## Test Cases

Amounts are in MON. All cases use `K = 3` and `DEFAULT_RESERVE = 10`.

### Record handling

Account `X` is unconfigured before block 100. Records are written as `(settledReserve, pendingReserve, validFrom)`.

| # | Action | Expected |
| --- | --- | --- |
| R1 | `getReserveBalance(X)` before any setter call | Returns `(10, 10, 0)`. All three slots are zero |
| R2 | `setReserveBalance(100)` by `X` in block 100 | Succeeds and returns `103`. Record is `(10, 100, 103)` |
| R3 | After R2: `getReserveBalance(X)` in blocks 100–102 | Returns `(10, 100, 103)` |
| R4 | After R2: a second `setReserveBalance(70)` by `X` in block 100 | Succeeds and returns `103`. Record is `(10, 70, 103)` |
| R5 | After R2: `setReserveBalance(80)` by `X` in block 101 or 102 | Fails. Record is unchanged |
| R6 | After R2: `getReserveBalance(X)` in block 103 or later | Returns `(100, 100, 0)`. The stored record is still `(10, 100, 103)` |
| R7 | After R2: `setReserveBalance(90)` by `X` in block 103 | Succeeds and returns `106`. Record is `(100, 90, 106)`. The active reserve stays 100 through block 105 |
| R8 | `setReserveBalance` succeeds inside a call frame or transaction that then reverts | Record is unchanged |

### Call context

| # | Call | Expected |
| --- | --- | --- |
| C1 | `STATICCALL` to `getK`, `getReserveBalance`, or `setReserveBalance` | Fails |
| C2 | `DELEGATECALL` or `CALLCODE` to any new method | Fails |
| C3 | `CALL` to any new method within a static execution context | Fails |
| C4 | `CALL` to any new method with nonzero value | Fails |
| C5 | `setReserveBalance` with 35 or 37 bytes of calldata | Fails |
| C6 | `getReserveBalance` with a nonzero byte in the upper 12 bytes of the address word | Fails |
| C7 | Top-level transaction from an undelegated EOA to `0x1001` with `setReserveBalance(5)` calldata | Succeeds. The EOA’s record is updated |
| C8 | Delegated account `A` executes `CALL` to `setReserveBalance(5)` in a transaction paid for by `B` | Succeeds. `A`’s record is updated; `B`’s is not |
| C9 | Contract `H` executes `CALL` to `setReserveBalance(5)` when called by `A` | Succeeds. `H`’s record is updated; `A`’s is not |
| C10 | `CALL` to an account whose EIP-7702 delegation designator points to `0x1001` | Succeeds as empty code. No record is read or changed |

### Consensus accounting

Each case validates the listed blocks against the stated snapshot. Blocks not listed with a transaction are empty. "Budget" is the account’s remaining gas budget $G$.

Accounts:

- **Alice** is undelegated with balance 100. Her record is `(10, 100, 103)`: an increase scheduled in block 100. She is eligible for emptying in the candidate block unless the case says otherwise.
- **Erin** is delegated with balance 100 and the same record as Alice. She is never eligible for emptying.
- **Bob** is delegated with balance 100. His record is `(100, 10, 103)`: a reduction scheduled in block 100. He is never eligible for emptying.
- **Carol** is delegated, unconfigured, with balance 4.
- **Dave** is undelegated with balance 50 and an active reserve of 0. He is eligible for emptying in block 101.

Budget initialization and block-boundary caps:

| # | Account | Snapshot | Blocks | Expected budget |
| --- | --- | --- | --- | --- |
| G1 | Alice | $S_{100}$ | 101–103, all empty | 10 after each block. The increase at 103 does not replenish it |
| G2 | Alice | $S_{102}$ | 103–105, all empty | 10 after each block |
| G3 | Alice | $S_{103}$ | 104–106, all empty | 100 after each block |
| G4 | Bob | $S_{100}$ | 101–103, all empty | 100 after 101 and 102; 10 after 103 |

Transactions:

| # | Account | Snapshot | Transactions | Expected |
| --- | --- | --- | --- | --- |
| T1 | Alice | $S_{102}$ | Block 105: carries her own applied authorization, so not eligible for emptying; fee bound 20 | Inadmissible. Budget is 10 |
| T2 | Alice | $S_{103}$ | Block 106: the same transaction | Accepted. Budget is 80 |
| T3 | Alice | $S_{102}$ | Block 105: eligible for emptying; fee bound 20, value 30 | Accepted, since $20 \le 100$. Budget is $\min(100, 100 - 50) = 50$ |
| T4 | Alice | $S_{102}$ | After T3, same block: fee bound 60 | Inadmissible. Budget is 50 |
| T5 | Alice | $S_{102}$ | After T3, same block: fee bound 50 | Accepted. Budget is 0 |
| T6 | Erin | $S_{100}$ | Block 101: fee bound 6. Block 103: fee bound 5 | First accepted, budget 4. Second inadmissible: the cap at 103 is $\min(4, 100) = 4$ |
| T7 | Bob | $S_{100}$ | Block 102: fee bound 30. Block 103: fee bound 20 | First accepted, budget 70. Second inadmissible: the cap at 103 is $\min(70, 10) = 10$ |
| T8 | Bob | $S_{100}$ | Block 102: fee bound 30. Block 103: fee bound 10 | Both accepted. Budget is 0 |
| T9 | Carol | $S_{100}$ | Block 101: fee bound 5 | Inadmissible. Budget is $\min(4, 10) = 4$ |
| T10 | Carol | $S_{100}$ | Block 101: fee bound 4 | Accepted. Budget is 0 |
| T11 | Dave | $S_{100}$ | Block 101: eligible for emptying; fee bound 1, value 0. Then a second transaction with fee bound 1 | First accepted, budget $\min(0, 49) = 0$. Second inadmissible |
| T12 | Dave | $S_{100}$ | Block 101: eligible for emptying; fee bound 60 | Inadmissible, since $60 > 50$ |

### Execution check

"Reserve" is the account’s active reserve in the execution block.

| # | Account | Reserve | $B_{pre}$ | Fee bound | $B_{post}$ | Expected |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Delegated, not the sender | 5 | 8 | n/a | 4 | Violation: $4 < 5$ |
| E2 | Delegated, not the sender | 5 | 8 | n/a | 5 | No violation |
| E3 | Delegated, not the sender | 50 | 30 | n/a | 29 | Violation: $29 < 30$ |
| E4 | Delegated, not the sender | 50 | 30 | n/a | 30 | No violation |
| E5 | Sender, not eligible for emptying | 100 | 100 | 20 | 79 | Violation: $79 < 80$ |
| E6 | Sender, not eligible for emptying | 100 | 100 | 20 | 80 | No violation |
| E7 | Sender, not eligible for emptying | 0 | 100 | 20 | any | Violation: $20 > 0$. Cannot occur for a transaction accepted by consensus |
| E8 | Sender, eligible for emptying | 10 | 100 | 20 | 0 | No violation: exempt |
| E9 | Ordinary contract with a recorded configuration | 5 | 8 | n/a | 0 | No violation: not a protected account |

Thresholds and rollback:

| # | Scenario | Expected |
| --- | --- | --- |
| E10 | Delegated account with reserve 10 and $B_{pre} = 100$ calls `setReserveBalance(0)` and transfers out 95 in the same transaction | Violation: $5 < 10$. The setter does not lower the threshold for its own transaction. The record is unchanged after the revert |
| E11 | After a successful `setReserveBalance(0)` in block `b`, a later transaction in block `b` leaves the same account with 5 | Violation: the threshold in block `b` is still 10 |
| E12 | A delegated account’s balance falls to 0 during a transaction and is restored to its reserve before the final check | No violation |
| E13 | `dippedIntoReserve()` is called while the account in E12 is at 0, and again after it is restored | Returns `true`, then `false` |

## Reference Implementation

The following pseudocode illustrates record handling. `settled` is decoded from storage. It is not a complete client implementation; dispatch, gas, consensus replay, and EVM journaling are specified above.

```python
def active(record, block):
    if record.validFrom == 0:
        return DEFAULT_RESERVE
    if block < record.validFrom:
        return record.settled
    return record.pending

def query(record, block):
    current = active(record, block)
    if record.validFrom != 0 and block < record.validFrom:
        return current, record.pending, record.validFrom
    return current, current, 0

def schedule(record, block, reserve, k):
    assert(0 <= reserve < 2**256)
    assert(block <= 2**256 - 1 - k)
    validFrom = block + k

    if record.validFrom != 0 and block < record.validFrom:
        assert(record.validFrom == validFrom)
        settled = record.settled
    else:
        settled = active(record, block)

    return Record(settled, reserve, validFrom)
```

## Security Considerations

### Preservation of gas-payment guarantees

The critical invariant is that execution cannot remove funds already relied upon for consensus-admitted gas payments. Implementations must use the designated snapshot, apply reduction clamps at the correct boundary, preserve emptying debit history, and avoid granting a budget increase before its protection is reflected in the anchor state.

Updates made after the anchor block cannot mature within that anchor’s `K`-block window. A pending update already visible in the anchor cannot be changed by a later block before activation. These properties make the window’s reserve schedule knowable without executing its transactions.

### Authorization and wallet safety

The precompile authorizes the immediate account context, not the end user behind a delegated wallet. Delegated implementations must authenticate configuration requests. An unrestricted account execution module can otherwise select zero and impair self-funded operation, or select a very high reserve and restrict transfers.

Delegation changes do not reset configuration. Wallets should inspect an account’s existing record before assuming that replacing delegated code restores default behavior.

### Zero-reserve-balance recovery

A delegated account with zero reserve generally cannot originate a positive-fee transaction to raise its own reserve.

An authorized sponsored call can schedule a positive reserve. A wallet must retain a usable recovery path and account for the delay before the increased reserve contributes to its self-funded budget. An undelegated account can instead use an emptying transaction when eligible. With zero reserve, that is its only self-funded transaction until it is eligible again, because its budget after an emptying transaction is capped at zero.

## Open Questions

### Compatibility With MCP and Cadence

The design of this MIP is not inherently incompatible with MCP and the Cadence consensus architecture. As the design of MCP and Cadence crystallizes, another MIP will specify a revised design, likely built on similar mechanisms.

### Additional page read cost

Reserve balance accounting now requires loading an additional page (the one containing slot `s`), so gas repricing might be necessary. Options include changing the account-warming cost or repricing `CALL*`.

## Copyright

Copyright and related rights waived via CC0.
