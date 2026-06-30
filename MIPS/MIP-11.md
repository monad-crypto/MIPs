---
mip: 11
title: Automatic Priority Fee Distribution
description: Automatically distribute priority fees to delegators.
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-11-automatic-priority-fee-distribution/419
status: Draft
type: Standards Track
category: Core
created: 2026-04-01
---

## Abstract

This MIP automatically distributes priority fees and other transfers accumulated in the distribution account to delegators rather than crediting them solely to the validator's beneficiary address.

## Motivation

Currently, priority fees are credited directly to a validator's beneficiary address. In principle, a validator could forward these fees to its delegators by calling `externalReward` on the staking contract, but doing so is operationally cumbersome — it requires each validator to run additional infrastructure to sweep the beneficiary balance, manage gas for the forwarding transaction, and handle the `dust_threshold` minimum. In practice, most validators do not do this today, so priority fees accrue to the beneficiary rather than flowing through to delegators.

To ensure consistent compensation for all stakers without relying on per-validator tooling, this proposal introduces a mechanism that automatically distributes priority fees to delegators at the protocol level.

## Specification

### Overview

Automated priority fee distribution has two components:

1. A new account that captures priority fees and arbitrary user transfers, referred to as the `distribution account`. The address for the distribution account will be `0xfee5fee5fee5fee5fee5fee5fee5fee5fee5fee5`. 
2. End-of-block execution logic that attributes the balance accumulated in the `distribution account` to the corresponding validator pool modulo commission rate.

The `beneficiary` remains settable by the block proposer, and within the execution context, `block.coinbase` continues to refer to the beneficiary address.

### Execution Flow

The following changes are applied during block execution:

1. The beneficiary is still set by the block proposer and is still represented by `block.coinbase` in the execution context.
2. For each transaction, the priority fee is credited to the distribution account rather than to the beneficiary balance.
3. At the end of block execution, the system calls `distribute` on the distribution account. This function then forwards the fully accumulated balance to the staking contract if the minimal threshold is met.

The distribution account has the following logic:

```python
class distribution_account:

    # This function is only callable via execution; no transaction can call it.
    def distribute(address block_leader):
        
        # 1. Load Balance and clear balance per block
        total_balance = get_balance(address(this))
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
        
        # 5. Check if sufficent to distribute funds
        distribute_amount = total_balance - commission_amount
        if distribute_amount < DUST_THRESHOLD:
            exit 
            
        # 6. Distribute funds
        staking_contract.apply_commission_to_auth_account(auth){msg.value = commission_amount}
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

1. Blocks with zero priority fees result in a no-op distribution.
2. Small fee amounts must be validated against `dust_threshold`; Any distributable balance below dust_threshold is burned.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
