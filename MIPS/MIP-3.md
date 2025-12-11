---
mip: 3
title: Linear Memory
description: Redefine memory expansion cost to be linear and enforce an explicit maximum memory usage per transaction. 
author: Category Labs 
category: Core
created: 2025-12-10
---

## Abstract

Redefine memory expansion cost to be linear and enforce an explicit maximum memory usage per transaction. 

## Motivation

Currently, EVM memory usage is bounded by a quadratic expansion cost and the 63/64 rule. The theoretical memory limit of a transaction is at least 26 MB. Historical transaction analysis shows that average memory usage is ~2 KB and maximum observed memory usage is ~2 MB. 

Benchmarks also indicate that the current memory expansion formula overcharges for actual resource usage.

This update aligns cost with actual resource consumption. It makes memory usage more predictable, particularly for contracts that rely on large memory allocations.

## Specification

Memory expansion cost is redefined as:

```python
memory_size_words = (memory_byte_size + 31) // 32
memory_cost = 3 * memory_size_words 
```

The max memory usage is capped at 8 MB.  Memory allocation is bounded across call contexts with the following rule: 

1. Let `k` be the memory used by the current call, and `j` the memory used by parent calls.
2. The remaining memory available to a child call is: 

```python
 remaining_memory = 8 * 1024 * 1024 - j - k
```
3. Once a call returns, the memory is returned to the pool.
4. If a call exceeds the remaining memory limit, it reverts.
## Backwards Compatibility

This proposal is highly compatible with existing contracts. Almost all standard EVM operations remain valid and ERC-4337 contracts continue to function correctly, as child call memory is released upon completion. Replay testing of historical Ethereum transactions will be used to quantify compatibility.

However, contracts that allocate more than 8 MB of memory will now revert.

## Security Considerations

No security concerns were raised.

## Historical Reference

This is thematically similar to Vitalik’s EIP-7686 proposal. The main difference is that EIP-7686 defines a direct relationship between memory limit and gas limit.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).