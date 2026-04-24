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

This MIP automatically distributes priority fees to delegators rather than crediting them solely to the validator's beneficiary address.

## Motivation

Currently, priority fees are credited directly to a validator's beneficiary address. In principle, a validator could forward these fees to its delegators by calling `externalReward` on the staking contract, but doing so is operationally cumbersome — it requires each validator to run additional infrastructure to sweep the beneficiary balance, manage gas for the forwarding transaction, and handle the `dust_threshold` minimum. In practice, most validators do not do this today, so priority fees accrue to the beneficiary rather than flowing through to delegators.

To ensure consistent compensation for all stakers without relying on per-validator tooling, this proposal introduces a mechanism that automatically distributes priority fees to delegators at the protocol level.

## Specification

### Overview

Automated priority fee distribution has two components:

1. A new account that captures priority fees, referred to as the `distribution account`.
2. End-of-block execution logic that calls `external_rewards` on the corresponding validator pool with the priority fees accumulated in the `distribution account`.

The `beneficiary` remains settable by the block proposer, and within the execution context, `block.coinbase` continues to refer to the beneficiary address.

### Execution Flow

The following changes are applied during block execution:

1. The beneficiary is still set by the block proposer and is still represented by `block.coinbase` in the execution context.
2. For each transaction, the priority fee is credited to the distribution account rather than to the beneficiary balance.
3. At the end of block execution, the system calls `syscall_distribute` on the distribution account. This function forwards the full accumulated balance to the staking contract via `external_rewards`.

The distribution account has the following logic:

```python
class distribution_account:

    # This function is only callable via execution; no transaction can call it.
    def syscall_distribute(address block_leader):
        priority_fees = get_balance(address(this))

        # Same value as the val_id used by syscall_reward for block_leader.
        val_id = staking_contract.val_id(block_leader)

        # Sub-threshold fees are filtered by external_rewards (see dust_threshold).
        staking_contract.external_rewards(val_id){msg.value = priority_fees}
```

## Rationale

Priority fees are a component of validator revenue, and delegators should receive a share of this allocation in return for helping secure the network.

This design ensures:

1. Native inclusion of priority fees within staking rewards.
2. Elimination of any reliance on off-chain or external distribution logic.

## Backwards Compatibility

This change modifies the flow of priority fees: they will no longer appear in the balance of `block.coinbase` as a direct credit.

Because priority fees are now distributed to all delegators within a validator's pool, third-party delegation contracts may be affected. Such contracts will experience a dilution in their share of priority fees if users bypass the external contract and stake directly with the validator pool.

To be amenable to this update `external_rewards` will be modified so that it removes the commission fee when called. 

## Security Considerations

The primary consideration is the precision of the reward accumulator.

`external_rewards` requires a minimum input amount, defined as the `dust_threshold`, in order to guarantee a certain decimal accuracy within the accumulator. The minimum threshold for non-zero priority fees must align with this `external_rewards` minimum-balance requirement, and any fees below this threshold will not be distributed.

Edge cases to consider:

1. Blocks with zero priority fees result in a no-op distribution.
2. Small fee amounts must be validated against `dust_threshold`; sub-threshold fees are burned.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
