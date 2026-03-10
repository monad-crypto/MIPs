---
mip: 7
title: Extension opcodes
description: Add a reserved opcode for implementation-defined extension opcodes
author: Category Labs
category: Core
created: 2026-01-28
---

## Abstract

This MIP proposes a new opcode `EXTENSION` (`0xAE`) that can be used to extend the Monad VM with new opcode-level features, while minimizing the risk of collision with future changes to the Ethereum execution layer. This MIP aligns with [EIP-8163](https://eips.ethereum.org/EIPS/eip-8163), which reserves the same opcode on Ethereum L1.

## Motivation

At present, bytecode execution in the Monad VM is fully Ethereum-compatible: all Ethereum opcodes are supported, and there are no additional opcodes implemented by Monad that are not present in Ethereum. However, in the future, new features will be proposed for Monad that warrant the addition of new opcodes. For example, an early version of [MIP-4](./MIP-4.md) specified the addition of an opcode to inspect the state of Monad's reserve balance mechanism. While that MIP rejected the opcode-based design in favour of a precompile, the design decisions discussed in relation to that early version prompted this MIP.

EIP-8163 reserves the `EXTENSION` (`0xAE`) opcode on Ethereum L1 specifically to enable non-L1 EVM chains to safely experiment with extensions without risking future incompatibility. This MIP adopts that reservation for Monad.

## Specification

Add a new opcode `EXTENSION` (`0xAE`). On Monad, this opcode is reserved for use by future MIPs that define specific extension opcodes. Until amended by future MIPs, `EXTENSION` should behave as if `INVALID` (`0xFE`) had been executed. No specific encoding scheme for extension arguments is defined by this MIP; future MIPs may propose encodings as needed.

### Gas Costs

No gas costs for individual extension opcodes are proposed by this MIP. Any invalid or undefined extension opcode should cost the same as executing `INVALID` (consume all gas and revert).

### `JUMPDEST` Analysis

As specified by EIP-8163, `JUMPDEST` analysis MUST be unaffected by `EXTENSION`. The `0xAE` byte does not change the validity of any subsequent `JUMPDEST` (`0x5B`) bytes. Any future extension encoding that uses `0x5B` as an immediate argument byte — where that byte would also be a valid `JUMPDEST` — MUST cause execution to fail.

## Rationale

Several alternative designs were considered:

### No Extension

In this design, new implementation-specific opcodes are simply allocated to unused bytes in the existing EVM opcode space. This design is simple from an implementation perspective, but risks collision with future Ethereum upgrades. If such a collision were to occur, it is likely that a more complex resolution would be required, or that Monad would have to accept a permanent break of compatibility with Ethereum. A single reserved extension opcode reduces this risk substantially.

### Immediate Encoding like `PUSH1`

The currently accepted approach to introducing opcodes with immediate arguments is to do so in a `JUMPDEST` analysis preserving way.

An earlier version of this MIP proposed that `EXTENSION` carry a single-byte immediate operand (structurally identical to `PUSH1`), forming a two-byte `0xAEXX` instruction and skipping over the `XX` byte during `JUMPDEST` analysis. This conflicts with `JUMPDEST` analysis preservation and compromises code portability across chains.

### Stack-based

Rather than encoding extension arguments as immediate data, an alternative would be to pop the implementation-specific opcode from the stack. Doing so has the advantage of simpler upstream compatibility. The main downside of this approach is performance: popping a 32-byte word from the stack, interpreting it as an opcode, and dispatching on it would exit the hot path of typical interpreter designs. However, it is worth noting that the Monad VM's native-code compiler could trivially inline the presumed common pattern of `PUSH1 0xXX; EXTENSION` with zero overhead.

Additionally, stack-based dispatch would allow opcode selection to come from runtime data or computation, preventing static analysis of stack contents and extension behavior, and hindering EVM execution optimization.

### Precompiles

Some features could potentially be implemented either as new opcodes or as precompiles: adding precompiles is less risky from a collision perspective, but calling precompiles incurs additional overhead for ABI compatibility that may not be viable for all features.

## Backwards Compatibility

The opcode `0xAE` is currently invalid in both Ethereum and Monad. Since `JUMPDEST` analysis is unaffected by `EXTENSION`, no existing code behavior changes.

## Security Considerations

Because `JUMPDEST` analysis is unaffected by `EXTENSION`, the risks associated with divergent jump analysis between Monad and Ethereum are mitigated. On both chains, `0xAE` followed by `0x5B` results in the `0x5B` remaining a valid `JUMPDEST`. Any future extension encoding must ensure that `JUMPDEST` bytes within immediate arguments cause execution failure, preventing ambiguous control flow.

## References

- [EIP-8163: Reserve EXTENSION (0xAE) Opcode](https://eips.ethereum.org/EIPS/eip-8163)
- [Monad Initial Specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
