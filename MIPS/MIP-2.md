---
mip: 2
title: Increase Contract Code Size Limit
description: Increase the maximum contract code size limit to 128 KB and initcode size limit to 256 KB
author: QEDK (@qedk), et al.
discussions-to:
status: Final
type: Standards Track
category: Core
created: 2026-02-26
---

## Abstract

Increase the maximum contract code size (`MAX_CODE_SIZE`) from 24,576 bytes (24 KB) to 131,072 bytes (128 KB), and correspondingly increase the maximum initcode size (`MAX_INITCODE_SIZE`) from 49,152 bytes (48 KB) to 262,144 bytes (256 KB).

## Motivation

[EIP-170](https://eips.ethereum.org/EIPS/eip-170) introduced a contract code size limit of 24,576 bytes to mitigate a potential denial-of-service vector: calling a contract incurs O(n) cost in disk reads, VM preprocessing, and Merkle proof generation relative to the contract's code size, none of which is directly compensated by gas. While this limit was reasonable given Ethereum's constraints at the time of the Spurious Dragon hard fork, it has become a significant obstacle for developers building complex applications.

Modern smart contract development frequently encounters the 24 KB ceiling. Complex DeFi protocols, on-chain order books, sophisticated governance systems, and contracts with rich error reporting routinely exceed this limit, forcing developers to adopt workarounds such as proxy patterns (e.g. [EIP-2535](https://eips.ethereum.org/EIPS/eip-2535)), library-based architectures using `DELEGATECALL`, or splitting application logic across multiple contracts. These workarounds increase deployment complexity, introduce additional gas overhead for cross-contract calls, and expand the attack surface through the use of proxies.

Monad's architecture fundamentally changes the resource cost calculus that motivated the original limit. Monad's custom database (MonadDB) is optimized for fast state access from SSD, and Monad's native-code JIT compiler amortizes the cost of bytecode preprocessing across repeated contract invocations. Together, these optimizations ensure that loading and executing larger contracts does not impose a disproportionate burden on validators relative to gas fees paid. Additionally, Monad enforces a per-transaction gas limit of 30M gas, which inherently constrains the resource impact of any single contract interaction.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Parameters

| Constant | Previous Value | New Value |
|---|---|---|
| `MAX_CODE_SIZE` | 24,576 (0x6000) | 131,072 (0x20000) |
| `MAX_INITCODE_SIZE` | 49,152 (0xC000) | 262,144 (0x40000) |

### Contract Creation

As defined in [EIP-170](https://eips.ethereum.org/EIPS/eip-170), if contract creation initialization returns data with length of more than `MAX_CODE_SIZE` bytes, contract creation MUST fail with an out-of-gas error. This applies to all contract creation contexts: top-level creation transactions, `CREATE` (0xf0), and `CREATE2` (0xf5).

### Initcode Size

If the length of initcode exceeds `MAX_INITCODE_SIZE`, the transaction or instruction MUST be treated as invalid, consistent with [EIP-3860](https://eips.ethereum.org/EIPS/eip-3860). For creation transactions, this means the transaction is invalid. For `CREATE` and `CREATE2` instructions, execution MUST fail with an out-of-gas error.

The initcode cost defined by EIP-3860 remains unchanged:

```python
INITCODE_WORD_COST = 2
initcode_cost = INITCODE_WORD_COST * ceil(len(initcode) / 32)
```

### Code Deployment Cost

The per-byte code deposit cost of 200 gas per byte, as originally defined in the Ethereum Yellow Paper, remains unchanged.

## Rationale

### Choice of 128 KB

The new limit of 128 KB (131,072 bytes) represents a ~5.3x increase over the Ethereum default. This value was chosen to provide substantial headroom for complex contracts without introducing unbounded resource consumption. At the deployment cost of 200 gas per byte, deploying a maximum-size contract requires approximately 26.2M gas for the code deposit alone, which fits within Monad's 30M per-transaction gas limit while leaving room for initialization logic.

Some alternatives were considered:

- **64 KB**: Proposed for Ethereum in [EIP-7830](https://github.com/ethereum/EIPs/blob/d434180a40093c8ece93db9d98c7963a3cfdddf9/EIPS/eip-7830.md) (for EOF contracts)
- **64 KB and gas metering**: Proposed for Ethereum in [EIP-7907](https://github.com/ethereum/EIPs/blob/d434180a40093c8ece93db9d98c7963a3cfdddf9/EIPS/eip-7907.md) (with metering for excess code loading)

Monad's optimized storage and execution layers permit a more aggressive limit. 128 KB was selected as a practical upper bound: large enough to accommodate the most complex foreseeable single-contract deployments, while small enough to remain well within the gas budget and to avoid requiring changes to storage or networking assumptions.

### Initcode Limit

`MAX_INITCODE_SIZE` is set to `2 * MAX_CODE_SIZE` (262,144 bytes), preserving the relationship established by [EIP-3860](https://eips.ethereum.org/EIPS/eip-3860). Initcode may be larger than deployed code because it includes constructor logic and immutable variable encoding that is not retained in the final bytecode.

### No Additional Gas Metering

Unlike EIP-7907, this MIP does not introduce additional gas metering for loading large contract code (e.g. cold code access surcharges). Monad's storage architecture and JIT compilation make the marginal cost of loading larger code negligible relative to existing gas costs. Should future analysis indicate otherwise, additional metering can be introduced in a subsequent MIP.

## Backwards Compatibility

This change is backwards-compatible. All contracts valid under the previous 24,576-byte limit remain valid. Contracts between 24,576 and 131,072 bytes that could not previously be deployed on Monad can now be deployed successfully.

Contracts deployed on Ethereum or other EVM chains with code sizes exceeding 24,576 bytes (if any exist through non-standard means) can be redeployed on Monad without issue.

## Security Considerations

Increasing the contract code size limit raises the maximum resource cost of operations that scale with code size, such as `EXTCODECOPY`, disk reads, and VM preprocessing. However, Monad mitigates these costs through:

- **MonadDB**: Optimized SSD-based state storage reduces the marginal cost of reading larger contracts.
- **JIT compilation**: Frequently-used contracts are compiled to native code, amortizing preprocessing costs.
- **Per-transaction gas limit**: The 30M per-transaction gas cap bounds the total resource expenditure of any single transaction.

RPC node operators should be aware that concurrent `eth_call` invocations involving large contracts may consume additional memory. Operators MAY adjust concurrency limits accordingly to avoid out-of-memory conditions.

## References

- [EIP-170: Contract code size limit](https://eips.ethereum.org/EIPS/eip-170)
- [EIP-3860: Limit and meter initcode](https://eips.ethereum.org/EIPS/eip-3860)
- [EIP-7830: Contract size limit increase for EOF](https://github.com/ethereum/EIPs/blob/d434180a40093c8ece93db9d98c7963a3cfdddf9/EIPS/eip-7830.md)
- [EIP-7907: Meter Contract Code Size And Increase Limit](https://github.com/ethereum/EIPs/blob/d434180a40093c8ece93db9d98c7963a3cfdddf9/EIPS/eip-7907.md)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
