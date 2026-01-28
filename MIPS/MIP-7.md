---
mip: 7
title: Extension opcodes
description: Add a reserved two-byte opcode family for implementation-defined extension opcodes
author: Category Labs
category: Core
created: 2026-01-28
---

## Abstract

This MIP proposes a new 2-byte opcode `EXTENSION` (`0xEEXX`, where `XX` is a single byte immediate operand) that can be used to extend the Monad VM with new opcode-level features, while minimizing the risk of collision with future changes to the Ethereum execution layer.

## Motivation

At present, bytecode execution in the Monad VM is fully Ethereum-compatible: all Ethereum opcodes are supported, and there are no additional opcodes implemented by Monad that are not present in Ethereum. However, in the future, new features will be proposed for Monad that warrant the addition of new opcodes. For example, an early version of [MIP-3](./MIP-3.md) specified the addition of an opcode to inspect the state of Monad's reserve balance mechanism. While that MIP rejected the opcode-based design in favour of a precompile, the design decisions discussed in relation to that early version prompted this MIP.

## Specification

Add a new opcode `0xEE` that carries a single-byte immediate operand (structurally identical to `PUSH1`). The immediate operand is intended to encode a Monad-specific opcode value. No such opcodes are proposed by this MIP: until amended by future MIPs, all extension opcodes should behave as if `INVALID` had been executed.

### Gas Costs

No gas costs for individual extension opcodes are proposed by this MIP. Any invalid extension opcode should cost the same as executing `INVALID` (consume all gas and revert).

### `JUMPDEST` Analysis

As for `PUSHN` family opcodes, an immediate data byte of `0x5B` following a `0xEE` byte is not a valid jump destination.

## Rationale

The choice of `0xEE` as the extension opcode is aesthetic (`0xEEXX` resembles "extension"), but this choice is arbitrary and could be moved to the most agreeable unused opcode.

Several alternative designs were considered:

### No Extension

In this design, new implementation-specific opcodes are simply allocated to unused bytes in the existing EVM opcode space. This design is simple from an implementation perspective, but risks collision with future Ethereum upgrades. If such a collision were to occur, it is likely that a more complex resolution would be required, or that Monad would have to accept a permanent break of compatibility with Ethereum. A single reserved extension opcode reduces this risk substantially.

### Stack-based

Rather than having an immediate data byte follow the `0xEE` opcode, an alternative would be to pop the implementation-specific opcode from the stack. Doing so has the advantage of simpler upstream compatibility: no changes to Ethereum jump destination analysis would be required (only a reservation of `0xEE` would be necessary). The main downside of this approach is performance: popping a 32-byte word from the stack, interpreting it as an opcode, and dispatching on it would exit the hot path of typical interpreter designs. However, it is worth noting that the Monad VM's native-code compiler could trivially inline the presumed common pattern of `PUSH1 0xXX; EXTENSION` with zero overhead.

### Precompiles

Some features could potentially be implemented either as new opcodes or as precompiles: adding precompiles is less risky from a collision perspective, but calling precompiles incurs additional overhead for ABI compatibility that may not be viable for all features.

## Backwards Compatibility

The opcode `0xEE` is currently invalid in both Ethereum and Monad. Backwards compatibility issues would be limited to contract code that formed the sequence `0xEE5B`; in this case, jump destination analysis would change the semantics of that code (see Security Considerations below).

## Security Considerations

If this opcode is not adopted by Ethereum, it would be trivial to construct contract code that behaves meaningfully differently on Monad vs. Ethereum via `JUMPDEST` handling: the bytecode sequence `0xEE5B` would form `INVALID; JUMPDEST` on Ethereum, but `EXTENSION 0x5B` on Monad.

## References

- [Monad Initial Specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
