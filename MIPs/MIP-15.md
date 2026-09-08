---
mip: 15
title: Glamsterdam EIP Activation
description: Activate selected EIPs from Ethereum's Glamsterdam upgrade.
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-15-glamsterdam-eip-activation/540
status: Review
type: Standards Track
category: Core
created: 2026-08-18
---

## Abstract

Activate six EIPs from Ethereum's Glamsterdam upgrade ([EIP-7773]):
[EIP-7708], [EIP-7843], [EIP-7981], [EIP-7997], [EIP-8024] and [EIP-8246].

## Specification

This MIP activates the following EIPs:

- [EIP-7708] — ETH transfers emit a log
- [EIP-7843] — SLOTNUM opcode
- [EIP-7981] — Increase Access List Cost (modified, see below)
- [EIP-7997] — Deterministic Factory Contract
- [EIP-8024] — Backward compatible SWAPN, DUPN, EXCHANGE
- [EIP-8246] — Remove SELFDESTRUCT Burn

[EIP-7981] is adopted with `access_list_data_cost = 40 * access_list_bytes`
(800 gas per address and 1280 gas per storage key) rather than 64 gas per byte.

All other EIPs included in Glamsterdam ([EIP-7773]) are not activated; see
[Rationale](#rationale).

### Chain Specifics

[EIP-7997] has no effect on Monad Mainnet or Testnet: the deterministic factory
contract has already been deployed on those networks via the usual keyless
transaction method. Adopting the EIP therefore only affects local development
networks.

## Rationale

Block-level access lists are incompatible with Monad's asynchronous execution
model. Proposers do not execute blocks, and so cannot reliably populate the
access lists. [EIP-7928] is therefore not adopted by Monad:

- [EIP-7928] — Block-Level Access Lists

The following EIPs deal with the Ethereum consensus layer and are therefore not adopted by Monad:

- [EIP-8045] — Exclude slashed validators from proposing
- [EIP-8061] — Increase exit and consolidation churn
- [EIP-8282] — Builder Execution Requests
- [EIP-7688] — Forward compatible consensus data structures
- [EIP-7732] — Enshrined Proposer-Builder Separation

The following EIPs establish a new two-dimensional gas model for Ethereum. Monad
may make different choices regarding gas metering in the future, and so at this
time the protocol will not adopt the Ethereum changes in these EIPs:

- [EIP-2780] — Resource-based intrinsic transaction gas
- [EIP-7778] — Block Gas Accounting without Refunds
- [EIP-7976] — Increase Calldata Floor Cost
- [EIP-8037] — State Creation Gas Cost Increase
- [EIP-8038] — State-access gas cost update

Since [EIP-7976] is not adopted, the access list data cost in [EIP-7981] is set
to match Monad's existing calldata floor cost of 40 gas per byte, rather than the
increased Ethereum floor of 64.

On Monad, the maximum contract size is already 128KB. The increase in [EIP-7954]
is therefore not adopted:

- [EIP-7954] — Increase Maximum Contract Size

The networking EIPs in [EIP-7773] concern Ethereum's devp2p protocols, which
Monad does not use, and its informational EIPs specify no protocol changes;
neither group is adopted.

## Backwards Compatibility

No backwards compatibility issues beyond those in the original EIP specifications.

## Security Considerations

No security considerations beyond those in the original EIP specifications.

## References

- [EIP-7773] — Hardfork Meta - Glamsterdam
- [Monad Initial Specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).

<!-- EIP link index -->

[EIP-2780]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-2780.md
[EIP-7688]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7688.md
[EIP-7708]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7708.md
[EIP-7732]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7732.md
[EIP-7773]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7773.md
[EIP-7778]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7778.md
[EIP-7843]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7843.md
[EIP-7928]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7928.md
[EIP-7954]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7954.md
[EIP-7976]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7976.md
[EIP-7981]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7981.md
[EIP-7997]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-7997.md
[EIP-8024]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-8024.md
[EIP-8037]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-8037.md
[EIP-8038]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-8038.md
[EIP-8045]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-8045.md
[EIP-8061]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-8061.md
[EIP-8246]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-8246.md
[EIP-8282]: https://github.com/ethereum/EIPs/blob/b6d3f2c65aad65bb09856db6db50ae612b8bf8aa/EIPS/eip-8282.md
