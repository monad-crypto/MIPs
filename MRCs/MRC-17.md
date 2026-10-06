---
mip: 17
title: PropAMM Router Interface
description: Minimal routing interface for proprietary AMMs
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mrc-17-propamm-routing-interface/
status: Draft
type: Standards Track
category: MRC
created: 2026-09-28
---

## Abstract

This MRC defines a standard routing interface for proprietary automated market makers (“propAMMs”). A compatible propAMM or its adapter contract exposes functions for exact input quoting and swap execution. Quotes may return opaque venue-specific data that is passed back during execution.

The standard defines functions that are mainly used by onchain aggregators. The propAMM internal mechanisms are not enforced by this proposal.

## Motivation

PropAMMs derive prices following different mechanisms: from venue-specific logic, oracle updates, offchain market-making systems, signed price commitments, inventory constraints, or other custom mechanisms rather than a pre-defined onchain curve.

This flexibility creates fragmentation for routers and onchain aggregators as existing venues expose different interfaces. Without a common interface, every router must implement and maintain an integration code specific to a single propAMM.

Common integration frictions include:

1. **Non-standard quote functions:** propAMMs expose different input conventions, return values, and some of them do state mutation during asset quoting.
2. **Non-standard swap functions:** swap interfaces vary in direction encoding, recipient semantics, slippage checks, and callbacks, etc.
3. **Inconsistent token transfer:** some venues transfer the input token from addresses via allowance, while others expect tokens to be explicitly transferred before swap execution.
4. **Requirement of supplementary data for swap execution:** certain propAMMs require signed prices or quote identifiers to execute a swap.
5. **Different deployment architectures:** propAMMs may use per-pair contracts, others follow the singleton design.

This MRC allows onchain aggregators to quote and execute swaps via any propAMM contract or adapter through one interface without implementing any venue-specific logic.

## Specification

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “NOT RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in RFC 2119 and RFC 8174.

### Interface

Every compatible propAMM contract MUST implement the following interface:

```solidity
/// @title Proprietary AMM Router Interface
/// @dev A contract may serve one or more markets.
///      `tokenIn` and `tokenOut` specify the requested assets and direction.
interface IPropAMMRouter {
    /// @notice Emitted after a successful swap.
    /// @param sender The caller that funded the swap.
    /// @param to The recipient credited with the output token.
    /// @param tokenIn The input token transferred from `sender`.
    /// @param tokenOut The output token credited to `to`.
    /// @param amountIn The exact input amount pulled from `sender`.
    /// @param amountOut The actual output amount credited to `to`.
    event PropAMMSwap(
        address indexed sender,
        address to,
        address indexed tokenIn,
        address indexed tokenOut,
        uint256 amountIn,
        uint256 amountOut
    );

    /// @notice Quotes an exact input swap.
    /// @param tokenIn The ERC-20 input token.
    /// @param tokenOut The ERC-20 output token.
    /// @param amountIn The exact input amount in base units of `tokenIn`.
    /// @param quoteData Opaque venue specific quote input, may be empty.
    /// @return amountOut The expected output amount in base units of `tokenOut`.
    /// @return swapData Opaque venue specific data to supply to `swap()`, may be empty.
    /// @dev This function is intentionally non-view. Routers that integrate
    ///      with `IPropAMMRouter` must execute it in a call frame whose state
    ///      changes are reverted.
    function getAmountOut(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        bytes calldata quoteData
    ) external returns (uint256 amountOut, bytes memory swapData);

    /// @notice Executes an exact input swap.
    /// @dev Before calling, `msg.sender` must grant this contract an ERC-20
    ///      allowance of at least `amountIn` for `tokenIn`. The contract
    ///      pulls exactly `amountIn` of `tokenIn` during this call and credits
    ///      the actual output in `tokenOut` to `to` before returning.
    /// @param tokenIn The ERC-20 input token.
    /// @param tokenOut The ERC-20 output token.
    /// @param to The recipient of the output token.
    /// @param amountIn The exact amount of `tokenIn` pulled from `msg.sender`.
    /// @param amountOutMin The minimum amount of `tokenOut` credited to `to`.
    /// @param deadline The timestamp after which the swap must revert.
    /// @param swapData Opaque venue specific execution data, may be empty.
    /// @return amountOut The actual amount of `tokenOut` credited to `to`.
    function swap(
        address tokenIn,
        address tokenOut,
        address to,
        uint256 amountIn,
        uint256 amountOutMin,
        uint256 deadline,
        bytes calldata swapData
    ) external returns (uint256 amountOut);
}
```

### Interface Scope and Asset Selection

A compatible `IPropAMMRouter` MAY be a native propAMM contract or an adapter and MAY represent one or more markets. `tokenIn` and `tokenOut` specify the market’s assets and swap direction.

Market discovery is outside the scope of this MRC. Implementations MAY expose additional getters, but routers SHALL NOT require such extensions to use the interface defined here. Discovery MAY be standardized separately.

### Caller and Taker Semantics

When an MRC-17 compatible contract is called through a router, `msg.sender` is the router and is the address from which the contract pulls input tokens. It is not necessarily the original token owner or the output token recipient.

Given that the interface does not include a separate taker input, A propAMM that have a dynamic pricing and swapping mechanism based on a taker input MAY use `quoteData` and `swapData` fields to encode the taker address.

### Quoting

The `getAmountOut()` returns the expected output for an exact input swap and any opaque data required to execute that quote.

If `swap()` is called by the same `msg.sender`, with the `tokenIn`, `tokenOut` and `amountIn`, using the returned `swapData`, before its expiry and without relevant venue state changes, the MRC-17 compatible contract MUST be capable of delivering at least the quoted `amountOut`.

`getAmountOut()` is intentionally non-view and is not required to be called using the `STATICCALL` opcode. An MRC-17-compatible propAMM MAY apply state changes before returning a quote, including executing a swap that deliberately reverts and bubble up its result through revert data.

If the `swapData` returned by `getAmountOut()` is relied on during `swap()` execution, then it MUST be valid when `swap()` is invoked as long as it’s not expiring and not impacted by state changes.

### Swap Execution

`swap()` executes an exact input swap through the conforming contract.

Requirements:

- `amountIn` MUST be interpreted as the exact input amount.
- `amountOutMin` MUST be interpreted as the minimum actual output amount credited to `to`.
- `to` MUST NOT be the zero address.
- `deadline` MUST be enforced by the conforming contract. If `block.timestamp > deadline`, the call MUST revert.
- `swapData` is opaque to the router and MAY contain venue specific execution data.
- Before calling `swap()`, `msg.sender` MUST grant the conforming contract an ERC-20 allowance of at least `amountIn` for the input token.
- During `swap()`, the conforming contract MUST transfer exactly `amountIn` of the input token from `msg.sender` using ERC-20 `transferFrom` semantics, with the contract acting as the approved spender.
- The conforming contract MUST NOT require input tokens to be transferred before `swap()` is called.
- The conforming contract MUST NOT use a pre existing token balance as a substitute for transferring `amountIn` from `msg.sender` for the current invocation.
- The actual `amountOut` MUST be at least `amountOutMin`, otherwise the conforming contract MUST revert.

Recipient and deadline validation are under the MRC obligations. A compatible propAMM contract MUST enforce them independently for every caller and MUST NOT rely on the router to validate either value.

### Token Semantics

This MRC defines behavior in terms of ERC-20 allowances and transfers. Native assets MUST be represented by an ERC-20 compatible wrapped token.

Fee on transfer, rebasing, or otherwise non standard tokens are compatible only if the contract normalizes their behavior and still satisfies every exact input and actual output requirement in this specification.

### Exact Input Only

This interface is a standard for exact input quoting and execution only. Exact output swaps are excluded from the base interface because they are not supported by every propAMM venue.

Implementations MAY expose exact output methods outside this MRC.

### Events

A compatible contract SHOULD emit the `PropAMMSwap` event after each successful `swap()`.

In `PropAMMSwap`:

- `sender` MUST equal the `msg.sender` that invoked `swap()`
- `to` MUST equal the output recipient passed to `swap()`
- `tokenIn` and `tokenOut` MUST equal the corresponding arguments passed to `swap()` and identify the actual input and output assets.
- `amountIn` MUST equal the exact input amount transferred from `sender`
- `amountOut` MUST equal the actual output amount credited to `to`

For routed swaps, `sender` is normally the integrating router rather than the actual taker. A propAMM contract MAY emit additional venue specific events containing the taker identity.

### Quote Isolation

Routers MUST treat every quote path as state changing and untrusted, even when a contract declares `getAmountOut` as `view`. Each quote MUST execute in an isolated child frame that reverts unconditionally after its success status and returndata have been captured.

When an integration leaves quote gas and returned data size unrestricted onchain, a candidate can exhaust the transaction’s available gas or cause the complete router request to fail. The offchain route or calldata generator MUST simulate the exact complete router call and enforce its resource policy before submitting the candidate set.

### Allowances and Token Custody

Routers integrating MRC-17 contracts SHOULD approve only the selected contract and SHOULD limit the allowance to the exact `amountIn` required for the current swap.

### Chain Specifics

This MRC defines an application layer interface and does not require a precompile, canonical deployment address, registry, or privileged implementation.

## Rationale

### Why a Routing Interface?

Standardizing propAMM contracts would force venues to redesign their core architecture.
A routing interface permits native propAMM contracts to conform directly, while a thin adapter gives existing venues a common integration target without changing their core mechanisms.

A popular design that aggregators rely on is directly using  the venue’s swap logic to retrieve the quote amount, by calling the swap function, reverting any state change in the call frame, decoding, and returning the swapped amount as a quote. Even for such aggregators that don’t rely on a quoting method, this proposal unifies the swap function and allows those aggregators to use the revert pattern without embedding any venue-specific logic.

### Why Explicit Input and Output Tokens

Explicit token addresses allow the same interface to support per-pair contracts and singleton venues that serve multiple markets. Routers specify the assets and direction directly, without requiring token-ordering getters or a separate adapter for every pair.

### Why `quoteData` and `swapData`?

propAMMs have different requirements across the quote to execution boundary. Some require no additional data, while others may require data such as signed prices, quote identifiers…etc

Opaque byte fields support these designs without requiring the standard to understand every venue specific format.

### Why is `getAmountOut` non-view?

Some venues derive quotes by using the same state changing logic used for execution and deliberately reverting after the output is known. These quote paths work under RPC `eth_call` but fail under EVM `STATICCALL`, even though their effects are intended to be discarded.

Making `getAmountOut` non-view permits aggregators to integrate those venues without reimplementing their pricing logic. Static compatible contracts remain valid and are still called successfully through an ordinary `CALL`.

### Why No Pair Discovery?

Discovery differs substantially between venues. Some use factories or singleton registries, while others rely on deterministic deployment. This MRC focuses only on the router facing quote and execution boundary.

## Backwards Compatibility

This MRC introduces a new application layer interface and does not modify existing contracts, the EVM, consensus or any existing token standard.

Existing propAMMs can integrate by deploying a wrapper for their quote and swap logic following the `IPropAMMRouter` interface.

## Security Considerations

The [quote isolation](#quote-isolation) requirements address state changes and resource exhaustion during quoting.
The [allowance and token custody](#allowances-and-token-custody) requirements limit approvals to the selected contract and the current swap's exact input.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
