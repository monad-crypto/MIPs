---
mip: 11
title: Automatic Priority Fee Distribution
description: Automatically distribute priority fees to delegators.
author: Category Labs (@category-labs)
discussions-to: https://forum.monad.xyz/t/mip-11-automatic-priority-fee-distribution/419
status: Review
type: Standards Track
category: Core
created: 2026-04-01
---

## Abstract

This MIP automatically distributes priority fees and other transfers accumulated in the distribution account to delegators rather than crediting them solely to the validator's beneficiary address.

## Motivation

Currently, priority fees are credited directly to a validator's beneficiary address. In principle, a validator could forward these fees to its delegators by calling `external_reward` on the staking contract, but doing so is operationally cumbersome — it requires each validator to run additional infrastructure to sweep the beneficiary balance, manage gas for the forwarding transaction, and handle the `dust_threshold` minimum. In practice, most validators do not do this today, so priority fees accrue to the beneficiary rather than flowing through to delegators.

To ensure consistent compensation for all stakers without relying on per-validator tooling, this proposal introduces a mechanism that automatically distributes priority fees to delegators at the protocol level.

## Specification

### Overview

Automated priority fee distribution has two components:

1.  A new account that captures priority fees and arbitrary user transfers, referred to as the `distribution account`. The address for the distribution account will be `0xfee5fee5fee5fee5fee5fee5fee5fee5fee5fee5`. 
2. A system transaction, inserted by consensus as the last transaction of every block and validated by execution, that distributes the balance accumulated in the `distribution account` to the corresponding validator pool, net of the validator's commission.

The `beneficiary` remains settable by the block proposer, and within the execution context, `block.coinbase` continues to refer to the beneficiary address. This does not affect distribution: the validator pool credited by the system transaction is determined by the block's proposer, not by the beneficiary. The proposer is not configurable. Consensus sets `block_leader` to the current proposer, and all nodes verify that it matches when validating the block. A proposer therefore cannot redirect delegators' priority fees by changing the beneficiary.

### Execution Flow

The following changes are applied during block execution:

1. The beneficiary is still set by the block proposer and is still represented by `block.coinbase` in the execution context.
2. For each transaction, the priority fee is credited to the distribution account rather than to the beneficiary balance.
3. Every block ends with exactly one distribution system transaction (see [System Transaction](#system-transaction)).
4. The system transaction calls `syscall_distribute` on the distribution account. This function pays the validator's commission and forwards the remaining balance to the staking contract if it is at least `dust_threshold`.
5. If the remaining balance is below `dust_threshold`, it is burned by `syscall_distribute`. If the balance is zero, the call is a no-op.

### System Transaction

The distribution is performed by a system transaction. Consensus inserts it and execution validates it. It follows the existing system transaction rules (see `syscall_reward`, `syscall_snapshot`, `syscall_on_epoch_change`), with the changes noted below.

**Insertion (consensus).** When constructing a block proposal, consensus appends exactly one distribution system transaction as the final transaction in the block, calling `syscall_distribute(block_leader)`. As with `syscall_reward`, consensus supplies `block_leader` in the calldata. Because consensus and execution are decoupled, consensus does not know the post-execution balance of the distribution account when the block is proposed. Priority fees can be determined statically, but the account can also receive arbitrary transfers during execution. The system transaction is therefore included unconditionally, and zero or below-`dust_threshold` balances are handled by `syscall_distribute` at execution time.

**Position.** Existing system transactions must precede all user transactions. The distribution system transaction is the single exception: it must be the last transaction in the block, so that it observes every priority fee and transfer credited to the distribution account during the block.

**Gas accounting.** Like all system transactions, the distribution system transaction has `gasLimit = 0` and `gasUsed = 0`, and pays no fees. Its effect on block gas accounting is therefore fully determined at proposal time, so consensus can construct it, and execution can validate it, before any state transitions are computed. It always succeeds; it cannot revert.

**Validation (execution).** Before executing the block, execution validates the system transactions in it. A block that fails validation is invalid.

```python
SYSTEM_SENDER = 0x6f49a8F621353f12378d0046E7d7e4b9B249DC9e

# Per-transaction checks shared by all system transactions.
def static_validate_system_tx(tx, sender):
    assert sender == SYSTEM_SENDER
    assert tx.type == LEGACY                    # type 0x0, chain-id protected
    assert tx.to is not None
    assert tx.to == expected_target(tx)         # STAKING_CA for staking syscalls,
                                                # DISTRIBUTION_ACCOUNT for syscall_distribute
    assert tx.gas_limit == 0
    assert tx.max_fee_per_gas == 0
    assert tx.max_priority_fee_per_gas == 0
    assert tx.authorization_list == []
    assert tx.nonce == state.get_nonce(SYSTEM_SENDER)

# Block-level ordering.
def static_validate_block_body(txs, senders):
    # 1. The block must end with exactly one distribution system tx.
    assert len(txs) >= 1
    last = txs[-1]
    assert senders[-1] == SYSTEM_SENDER
    assert selector(last) == SYSCALL_DISTRIBUTE
    assert last.value == 0

    # 2. All other system txs form a prefix of the block (existing rule).
    body = txs[:-1]
    body_senders = senders[:-1]
    n = count_leading(body_senders, SYSTEM_SENDER)
    assert SYSTEM_SENDER not in body_senders[n:]

    # 3. syscall_distribute appears nowhere else.
    assert all(selector(tx) != SYSCALL_DISTRIBUTE for tx in body[:n])

    # 4. Existing rules for the leading system txs are unchanged
    #    (at most one reward, reward value <= 25 MON, ...).
```

User transactions may not call `syscall_distribute`. Any call to it from a sender other than `SYSTEM_SENDER` reverts.

**Required changes to existing system transaction logic:**

1. Block validation currently rejects any system transaction after the first user transaction (`SystemTransactionNotFirstInBlock`). It must allow exactly one trailing `syscall_distribute` transaction.
2. System transaction validation currently requires `tx.to == STAKING_CA`. It must also accept `DISTRIBUTION_ACCOUNT` as the target of `syscall_distribute`.
3. System transaction dispatch must route the `syscall_distribute` selector to the distribution account logic below.

### Distribution Account

The distribution account has the following pseudocode logic:

```python
class distribution_account:

    # Only callable via the distribution system transaction (sender == SYSTEM_SENDER).
    def syscall_distribute(address block_leader):
       
        # 1. Load balance and clear balance per block
        total_balance = get_balance(address(this))
        if total_balance == 0:
            exit
        set_balance(address(this), 0) 
        
        # 2. Same value as the val_id used by syscall_reward for block_leader.
        val_id = staking_contract.val_id(block_leader)
        
        # 3. Get relevant validator info
        val_execution = val_execution(val_id)
        val_consensus = val_consensus(val_id)
        auth = delegator(val_id, val_execution.auth_address)

        # 4. Get Commission Fee if applicable 
        if val_consensus.commission_rate > 0:
            commission_amount = (total_balance * val_consensus.commission_rate) / 1e18
        else:
            commission_amount = 0 

        # 5. Check if sufficent to distribute funds
        distribute_amount = total_balance - commission_amount
        staking_contract.apply_commission_to_auth_account(auth){msg.value = commission_amount}
        
        # Below-threshold remainder is burned: the balance was already cleared
        # in step 1 and is not forwarded anywhere.
        if distribute_amount < DUST_THRESHOLD:
            exit

        # 6. Distribute funds and emit validator reward event
        staking_contract.distribute(val_id){msg.value = distribute_amount}
```

## Rationale

Priority fees are a component of validator revenue, and delegators should receive a share of this allocation in return for helping secure the network.

This design ensures:

1. Native inclusion of priority fees within staking rewards.
2. Elimination of any reliance on off-chain or external distribution logic.

## Backwards Compatibility

This change modifies the flow of priority fees: they will no longer appear in the balance of `block.coinbase` as a direct credit.

Because priority fees are now distributed to all delegators within a validator's pool, third-party delegation contracts may be affected. Such contracts will experience a dilution in their share of priority fees if users bypass the external contract and stake directly with the validator pool.


## Security Considerations

The primary consideration is the precision of the reward accumulator.

The constant `dust_threshold` was defined to guarantee a certain decimal accuracy within the accumulator. The minimum threshold for non-zero priority fees must align with the `dust_threshold` minimum-balance requirement. Any amount below this threshold will not be distributed and will be burned from the supply.

Edge cases to consider:

1. Blocks where the distribution account balance is zero still include the system transaction; `syscall_distribute` is a no-op and there is nothing to burn.
2. Small fee amounts must be validated against `dust_threshold`. Any distributable balance below dust_threshold is burned.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
