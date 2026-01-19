---
mip: 5
title: Fusaka EIP Activation
description: Activate EIP-7823, EIP-7883, and EIP-7939 from Ethereum's Fusaka upgrade.
author: Category Labs
category: Core
created: 2026-01-19
---

## Abstract

Activate three EIPs from Ethereum's Fusaka upgrade ([EIP-7607](https://eips.ethereum.org/EIPS/eip-7607)): EIP-7823, EIP-7883, and EIP-7939.

## Specification

This MIP activates the following EIPs:

- [EIP-7823: Set upper bounds for MODEXP](https://eips.ethereum.org/EIPS/eip-7823)
- [EIP-7883: ModExp Gas Cost Increase](https://eips.ethereum.org/EIPS/eip-7883)
- [EIP-7939: Count leading zeros (CLZ) opcode](https://eips.ethereum.org/EIPS/eip-7939)

### Excluded EIPs

The following EIPs are already activated by Monad:

- [EIP-7951: Precompile for secp256r1 Curve Support](https://eips.ethereum.org/EIPS/eip-7951)

The following EIPs pertain to Ethereum consensus layer and data availability, so
are not relevant to Monad:

- [EIP-7594: PeerDAS - Peer Data Availability Sampling](https://eips.ethereum.org/EIPS/eip-7594)
- [EIP-7917: Deterministic proposer lookahead](https://eips.ethereum.org/EIPS/eip-7917)
- [EIP-7918: Blob base fee bounded by execution cost](https://eips.ethereum.org/EIPS/eip-7918)

The following EIPs set parameters for which Monad makes different choices per [the Monad specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf) (30M
transaction gas limit, and 2MB block size), so are not included:

- [EIP-7825: Transaction Gas Limit Cap](https://eips.ethereum.org/EIPS/eip-7825)
- [EIP-7934: RLP Execution Block Size Limit](https://eips.ethereum.org/EIPS/eip-7934)

## References

- [Monad Initial Specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
