---
mip: 7
title: Extension opcodes
description: Add a reserved opcode for implementation-defined extension opcodes
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-7-extension-opcodes/387
status: Draft
type: Standards Track
category: Core
created: 2026-01-28
---

## Abstract

This MIP proposes a new opcode `EXTENSION` (`0xAE`) that can be used to extend the Monad VM with new opcode-level features, while minimizing the risk of collision with future changes to the Ethereum execution layer. It defines the encoding scheme for extended instructions, including the extension selector and two styles for encoding immediate arguments, and aligns with [EIP-8163](https://eips.ethereum.org/EIPS/eip-8163), which reserves the same opcode on Ethereum L1.

## Motivation

At present, bytecode execution in the Monad VM is fully Ethereum-compatible: all Ethereum opcodes are supported, and there are no additional opcodes implemented by Monad that are not present in Ethereum. However, in the future, new features will be proposed for Monad that warrant the addition of new opcodes. For example, an early version of [MIP-4](./MIP-4.md) specified the addition of an opcode to inspect the state of Monad's reserve balance mechanism. While that MIP rejected the opcode-based design in favour of a precompile, the design decisions discussed in relation to that early version prompted this MIP.

EIP-8163 reserves the `EXTENSION` (`0xAE`) opcode on Ethereum L1 specifically to enable non-L1 EVM chains to safely experiment with extensions without risking future incompatibility. This MIP adopts that reservation for Monad.

## Specification

### Extended Opcode Encoding

The `EXTENSION` opcode (`0xAE`) MUST be immediately followed by a 1-byte extension selector. The extension selector MUST NOT be `0x5B` (`JUMPDEST`) or in the range `0x60`-`0x7F` (`PUSH1`-`PUSH32`). An extension selector in this excluded range MUST cause an exceptional halt, consuming all remaining gas.

Define **extended opcode** as the 2-byte sequence `0xAE XX`.

Until a future MIP assigns meaning to a given selector, executing any extended opcode MUST behave as if `INVALID` (`0xFE`) had been executed.

### Argument Encoding

If a particular extension requires immediate arguments, future MIPs MUST use one of the two encoding styles:

#### Restricted-Range Immediates

Similar to [EIP-8024](https://eips.ethereum.org/EIPS/eip-8024), argument bytes follow the extended opcode directly:

```
0xAE XX a1 a2 ...
```

Each argument byte MUST NOT be `0x5B` or in the range `0x60`-`0x7F`. The number of argument bytes is fixed per extension selector and MUST be specified by the MIP that defines the extension.

#### PUSH-Prefix Immediates

Argument bytes are framed by a `PUSHx` byte (`0x60`-`0x7F`) that follows the extended opcode:

```
0xAE XX PUSHx b1 b2 ... bn
```

The `PUSHx` byte determines the argument length (n = opcode − `0x5F`). The full byte range `0x00`-`0xFF` is available.

In either encoding style, an extended opcode followed by incorrectly encoded bytes MUST behave as if `INVALID` (`0xFE`) had been executed.

## Rationale

Several alternative designs were considered:

### No Extension

In this design, new implementation-specific opcodes are simply allocated to unused bytes in the existing EVM opcode space. This design is simple from an implementation perspective, but risks collision with future Ethereum upgrades. If such a collision were to occur, it is likely that a more complex resolution would be required, or that Monad would have to accept a permanent break of compatibility with Ethereum. A single reserved extension opcode reduces this risk substantially.

### Selector Encoding like `PUSH1`

The currently accepted approach to introducing multibyte opcodes is to do so in a `JUMPDEST` analysis preserving way, following the precedent of [EIP-8024](https://eips.ethereum.org/EIPS/eip-8024). `JUMPDEST` analysis is unaffected by `EXTENSION` and by either of its argument encodings.

An earlier version of this MIP proposed that `EXTENSION` carry a single-byte immediate operand (structurally identical to `PUSH1`), forming a two-byte `0xAEXX` instruction and skipping over the `XX` byte during `JUMPDEST` analysis. This conflicts with `JUMPDEST` analysis preservation and compromises code portability across chains.

### Stack-based

Rather than encoding extension arguments as immediate data, an alternative would be to pop the implementation-specific opcode from the stack. Doing so has the advantage of simpler upstream compatibility. The main downside of this approach is performance: popping a 32-byte word from the stack, interpreting it as an opcode, and dispatching on it would exit the hot path of typical interpreter designs. However, it is worth noting that the Monad VM's native-code compiler could trivially inline the presumed common pattern of `PUSH1 0xXX; EXTENSION` with zero overhead.

Additionally, stack-based dispatch would allow opcode selection to come from runtime data or computation, preventing static analysis of stack contents and extension behavior, and hindering EVM execution optimization.

### Gas Costs

No gas costs for individual extension opcodes are proposed by this MIP. Any invalid or undefined extension opcode should cost the same as executing `INVALID` (consume all gas and revert).

### Choice of Immediates Encoding Style

This MIP leaves the choice of immediates encoding style to the particular selector. Restricted-range immediates are compact and suitable for short arguments that do not require the full byte range. PUSH-prefix immediates allow arbitrary byte values at the cost of an extra framing byte.

### Precompiles

Some features could potentially be implemented either as new opcodes or as precompiles: adding precompiles is less risky from a collision perspective, but calling precompiles incurs additional overhead for ABI compatibility that may not be viable for all features.

## Backwards Compatibility

The opcode `0xAE` is currently invalid in both Ethereum and Monad. Since `JUMPDEST` analysis is unaffected by `EXTENSION`, no existing code behavior changes.

## Security Considerations

Because `JUMPDEST` analysis is unaffected by `EXTENSION`, the risks associated with divergent jump analysis between Monad and Ethereum are mitigated. On both chains, `0xAE` followed by `0x5B` results in the `0x5B` remaining a valid jump destination.

## References

- [EIP-8163: Reserve EXTENSION (0xAE) Opcode](https://eips.ethereum.org/EIPS/eip-8163)
- [EIP-8024: Backward Compatible SWAPN, DUPN, EXCHANGE](https://eips.ethereum.org/EIPS/eip-8024)
- [Monad Initial Specification](https://category-labs.github.io/category-research/monad-initial-spec-proposal.pdf)

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
