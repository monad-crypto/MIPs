---
mip: 12
title: Decrease Vote Pace
description: Decrease consensus vote pace from 400ms to 300ms
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-12-decrease-vote-pace/488
status: Draft
type: Standards Track
category: Core
created: 2026-06-01
---

## Abstract

Decrease the consensus vote pace from 400ms to 300ms. Proportionally, decrease the following block parameters: transaction limit, proposal gas limit and proposal byte limit. Proportionally, also decrease the block reward.

## Specification

We propose the following changes to the chain parameters on the consensus client:

### Chain Parameters

| Chain Parameter | Current Value | Proposed Value |
| --- | --- | --- |
| vote_pace (ms)  | 400 | 300 |
| tx_limit | 5,000 | 3,750 |
| proposal_gas_limit | 200,000,000 | 150,000,000 |
| proposal_byte_limit | 2,000,000 | 1,500,000 |

We also propose the following change to the staking parameters, to roughly account for the more frequent block times:

### Staking Parameters

| Staking Parameter | Current Value | Proposed Value |
| --- | --- | --- |
| block_reward (MON)| 25 | 18 |

### Consensus and Execution Layer Impact

This change should not affect the execution client in any way.

The consensus client will vote on proposals 100 milliseconds faster than it does currently, leading to faster quorums and faster block times.

## Backwards Compatibility

This change is backward compatible with the execution client.

However, since the block parameters are used for consensus block validation, this change is not backward compatible with the consensus client and will require a hard fork on a round.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
