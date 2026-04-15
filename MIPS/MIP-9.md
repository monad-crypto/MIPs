---
mip: 9
title: Active Set Increase
description: Increase the `ACTIVE_VALSET_SIZE` from 200 to 300.
author: Jackson Lewis (@jacksononchain)
discussions-to: https://forum.monad.xyz/t/mip-9-active-set-increase/416
status: Draft
type: Standards Track
category: Core
created: 2026-03-19
---

## Abstract

This MIP proposes an increase to the maximum active validator set from 200 to 300.

The current active validator set is capped at 200. Raising the cap expands participation without introducing abrupt load changes to the consensus layer (MonadBFT) or execution pipeline.

## Specification

### Parameters

| Parameter | Current Value | Proposed Value |
|---|---|---|
| `ACTIVE_VALSET_SIZE` | 200 | 300 |

`ACTIVE_VALSET_SIZE` SHOULD be increased from 200 to 300.

### Consensus and Execution Layer Impact

This MIP affects the consensus layer (MonadBFT). The active validator set size directly governs the number of participants in each consensus round. The execution daemon is unaffected unless validator set membership is read by on-chain contracts, in which case any such contracts SHOULD be reviewed for compatibility.

The consensus daemon enforces `ACTIVE_VALSET_SIZE` as an upper bound on the number of validators eligible to participate in block proposal and voting at any given epoch. The selection mechanism for which validators fill the active set (e.g., by stake) is unchanged by this MIP.

## Rationale

An increment of 100 represents a meaningful expansion (~50%) without dramatically altering the message complexity in MonadBFT's voting rounds. Larger single-step increases carry higher risk of unforeseen performance degradation; smaller increments would add process overhead without proportionate benefit.

The increase allows for greater decentralization in the active set, enforcing stronger fault tolerance and economic security.

## Backwards Compatibility

This MIP does not introduce backwards incompatibilities. The change is additive: existing validators in the active set are unaffected. The hard-coded `ACTIVE_VALSET_SIZE = 200` MUST be updated to `300` to support the new parameter values prior to activation.

## Security Considerations

**Consensus scalability**: Increasing the active validator set increases the number of messages exchanged per consensus round in MonadBFT.

**Sybil risk**: Expanding the set without changes to the stake-based selection mechanism does not meaningfully increase Sybil risk. No additional mitigations are required.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
