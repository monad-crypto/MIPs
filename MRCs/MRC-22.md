---
mip: 22
title: Large Contract Deployment Factory
description: A deterministic factory contract for deploying large contracts with CREATEBIG
author: Category Labs (@category-labs)
discussions-to: https://forum.monad.xyz/t/mrc-22-large-contract-deployment-factory/595
status: Draft
type: Standards Track
category: MRC
created: 2026-11-05
requires: 21
---

## Abstract

[MIP-21](../MIPs/MIP-21.md) defines a new extended opcode (see [MIP-7](../MIPs/MIP-7.md)), `CREATEBIG`, that allows contracts of up to 256KiB to be deployed on Monad. Contract-creation transactions cannot use `CREATEBIG`, and existing compilers cannot emit it. This MRC specifies a deterministic factory contract at a canonical address through which both EOAs and contracts can deploy using the new opcode.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Overview

The factory is the contract with the creation bytecode given in [Bytecode](#bytecode), deployed at the address given in [Deployment](#deployment). It exposes a single method, `deploy`, which deploys initcode supplied in calldata using `CREATEBIG`. The behavior described in this section is that of the factory’s bytecode; where the two differ, the bytecode is authoritative.

The factory has two call modes, distinguished by the account in whose context its code executes. In both modes it holds no state.

### Interface

```solidity
interface ICreateBigFactory {
    /// @notice Deploys `initcode` using CREATEBIG.
    /// @dev In a direct call, `msg.value` must be at least `value + maxDepositValue`, and any value
    ///      not used for the endowment and deposit is refunded to the caller. In a delegated call,
    ///      the endowment and deposit are drawn from the calling contract's balance.
    /// @param salt The salt used for address derivation.
    /// @param initcode The initcode of the contract to deploy.
    /// @param value The value transferred to the new contract.
    /// @param maxDepositValue The maximum value that may be charged for the value-paid portion of the code deposit.
    /// @return deployed The address of the deployed contract.
    /// @return deposit The value charged for the value-paid portion of the code deposit.
    function deploy(bytes32 salt, bytes calldata initcode, uint256 value, uint256 maxDepositValue)
        external
        payable
        returns (address deployed, uint256 deposit);
}
```

| Kind     | Signature                               | Selector     |
| -------- | --------------------------------------- | ------------ |
| Function | `deploy(bytes32,bytes,uint256,uint256)` | `0xdc61e1cd` |

### Call Modes

A call is a *direct call* if `ADDRESS` equals the factory’s address, and a *delegated call* otherwise (for example, when a contract reaches the factory’s code via `DELEGATECALL`). A call made via `STATICCALL` fails, as `CREATEBIG` cannot execute in a static context.

Direct calls from EOAs with an EIP-7702 delegation behave as from any other caller. A delegated call made from the code of an EOA with an EIP-7702 delegation, including when an EOA delegates to the factory’s address, fails, as Monad does not permit contract creation from delegated EOA code.

#### Direct Calls

In a direct call, the factory is the deployer. It:

1. Decodes the arguments (see [Return Values and Errors](#return-values-and-errors)).
2. Derives the salt passed to `CREATEBIG` from `msg.sender` and `salt` (see [Address Derivation](#address-derivation)).
3. Reverts if `msg.value < value + maxDepositValue`, or if `value + maxDepositValue` overflows.
4. Executes `CREATEBIG` with the given `value`, `initcode` and `maxDepositValue`.
5. Computes the deposit charged (see [Deposit Funding](#deposit-funding)).
6. Transfers `msg.value - value - deposit`, if non-zero, to `msg.sender` with a `CALL` forwarding all remaining gas, and reverts if the call fails.
7. Returns `(deployed, deposit)`.

#### Delegated Calls

In a delegated call, the factory’s code executes as the calling contract, which is the deployer. The factory performs steps 1, 4, 5 and 7 above, passing `salt` to `CREATEBIG` unmodified. It does not check or refund `msg.value`: `CREATEBIG` checks and charges the calling contract’s own balance.

### Address Derivation

In a direct call, the deployed address is:

```txt
keccak256(0xff ++ factory ++ keccak256(abi.encode(msg.sender, salt)) ++ keccak256(initcode))[12:]
```

In a delegated call from contract `C`, the deployed address is that of `CREATE2` from `C`:

```txt
keccak256(0xff ++ C ++ salt ++ keccak256(initcode))[12:]
```

### Deposit Funding

The deposit returned by the factory is the value-paid portion of the code deposit charged by `CREATEBIG`, computed after deployment as:

```txt
deposit = (CODE_DEPOSIT_COST - PARTIAL_CODE_DEPOSIT_COST) * EXTCODESIZE(deployed) * block.basefee
```

with the parameters defined in MIP-21. In a direct call, the endowment and deposit are funded from `msg.value`, and the remainder is refunded. In a delegated call, they are funded from the calling contract’s balance.

### Return Values and Errors

On success, the factory returns `abi.encode(deployed, deposit)`.

The factory reverts with empty return data if:

- The first four bytes of calldata are not the `deploy` selector.
- The `initcode` length exceeds `MAX_DEPLOY_INITCODE_SIZE` (368,640 bytes).
- The arguments are not canonically ABI-encoded: the `initcode` offset is not `0x80`, or the calldata length is not exactly `164` plus the `initcode` length rounded up to a multiple of 32. Padding bytes are not checked.
- In a direct call, the value check in step 3 fails, or the refund in step 6 fails.

If `CREATEBIG` pushes `0`, the factory reverts with the return data of `CREATEBIG`: the constructor’s revert data if it reverted, and empty otherwise. If `CREATEBIG` halts exceptionally (for example, when the factory’s code is reached via `STATICCALL`), the factory’s call frame halts exceptionally.

Errors are not ABI-encoded, and empty revert data does not distinguish a failed factory check from a failed deployment.

### Bytecode

The factory is implemented in Yul as follows (also provided as [`CreateBigFactory.yul`](../assets/MRC-22/CreateBigFactory.yul)):

```yul
object "CreateBigFactory" {
    code {
        datacopy(0, dataoffset("runtime"), datasize("runtime"))
        setimmutable(0, "self", address())
        return(0, datasize("runtime"))
    }
    object "runtime" {
        code {
            // deploy(bytes32 salt, bytes initcode, uint256 value, uint256 maxDepositValue)
            if iszero(eq(shr(224, calldataload(0)), 0xdc61e1cd)) { revert(0, 0) }

            let salt            := calldataload(4)
            let value           := calldataload(68)
            let maxDepositValue := calldataload(100)
            let len             := calldataload(132)

            // initcode size limit (MIP-21 MAX_DEPLOY_INITCODE_SIZE); also prevents overflow below
            if gt(len, 368640) { revert(0, 0) }

            // strict ABI decoding: canonical offset, exact padded length
            if iszero(eq(calldataload(36), 0x80)) { revert(0, 0) }
            if iszero(eq(calldatasize(), add(164, and(add(len, 31), not(31))))) { revert(0, 0) }

            let direct := eq(address(), loadimmutable("self"))

            if direct {
                // bind salt to caller
                mstore(0, caller())
                mstore(32, salt)
                salt := keccak256(0, 64)
                let required := add(value, maxDepositValue)
                if lt(required, value) { revert(0, 0) }      // overflow
                if lt(callvalue(), required) { revert(0, 0) }
            }

            calldatacopy(0, 164, len)

            // CREATEBIG (MIP-21): EXTENSION (0xae), selector 0x02
            let deployed := verbatim_5i_1o(hex"ae02", value, 0, len, salt, maxDepositValue)
            if iszero(deployed) {
                returndatacopy(0, 0, returndatasize())
                revert(0, returndatasize())
            }

            // deposit = (CODE_DEPOSIT_COST - PARTIAL_CODE_DEPOSIT_COST) * |R| * basefee
            let deposit := mul(mul(extcodesize(deployed), 120), basefee())

            if direct {
                let refund := sub(callvalue(), add(value, deposit))
                if refund {
                    if iszero(call(gas(), caller(), refund, 0, 0, 0, 0)) { revert(0, 0) }
                }
            }

            mstore(0, deployed)
            mstore(32, deposit)
            return(0, 64)
        }
    }
}
```

#### Compiler Settings

| Setting     | Value                                 |
| ----------- | ------------------------------------- |
| Compiler    | `solc` 0.8.38 (`0.8.38+commit.1835d247`) |
| Mode        | `--strict-assembly`                   |
| Optimizer   | `--optimize` (default settings)       |
| EVM version | `osaka`                               |

#### Creation Bytecode

The creation bytecode (233 bytes) is:

```txt
0x60d8806100115f39305f603e01525ff3fe63dc61e1cd5f3560e01c0360ad576044356084356064356004356205a000831160ad5760806024350360ad5760a319601f8401601f191636030160ad577f00000000000000000000000000000000000000000000000000000000000000003014928360b9575b8060a45f375f85ae0290811560b157607848833b0202928391608e575b50505f5260205260405ff35b01340380609c575b82906082565b5f80808093335af11560ad575f6096565b5f80fd5b3d5f803e3d5ffd5b90335f5260205260405f209082850185811060ad573410156065575f80fd
```

Its keccak256 hash is `0x446b506632731122019daa6bbc668123567e05b1d9a719a864b4f72209995420`.

The runtime bytecode (216 bytes) is the creation bytecode from offset `0x11`, with the 32-byte immutable at runtime offset `0x3e` set to the factory’s own address by the constructor. The deployed runtime bytecode and its hash are given in [Deployment](#deployment).

### Deployment

The factory is deployed by a keyless, pre-EIP-155 contract-creation transaction ("Nick’s method"). The transaction’s signature is chosen rather than produced by a private key, so no party controls the sender account, and the factory has the same address on every network where the transaction is included.

The deployment transaction has the following fields:

| Field      | Value                                                                |
| ---------- | -------------------------------------------------------------------- |
| Type       | Legacy, without chain ID (pre-EIP-155)                               |
| `nonce`    | `0`                                                                  |
| `gasPrice` | `1000000000000` (1,000 gwei)                                         |
| `gasLimit` | `300000`                                                             |
| `to`       | Empty (contract creation)                                            |
| `value`    | `0`                                                                  |
| `data`     | The creation bytecode given in [Bytecode](#bytecode)                 |
| `v`        | `27`                                                                 |
| `r`        | `0x2222222222222222222222222222222222222222222222222222222222222222` |
| `s`        | `0x2222222222222222222222222222222222222222222222222222222222222222` |

The signed, RLP-encoded transaction is:

```txt
0xf9013b8085e8d4a51000830493e08080b8e960d8806100115f39305f603e01525ff3fe63dc61e1cd5f3560e01c0360ad576044356084356064356004356205a000831160ad5760806024350360ad5760a319601f8401601f191636030160ad577f00000000000000000000000000000000000000000000000000000000000000003014928360b9575b8060a45f375f85ae0290811560b157607848833b0202928391608e575b50505f5260205260405ff35b01340380609c575b82906082565b5f80808093335af11560ad575f6096565b5f80fd5b3d5f803e3d5ffd5b90335f5260205260405f209082850185811060ad573410156065575f80fd1ba02222222222222222222222222222222222222222222222222222222222222222a02222222222222222222222222222222222222222222222222222222222222222
```

| Item                    | Value                                                                |
| ----------------------- | -------------------------------------------------------------------- |
| Transaction hash        | `0xedc3bdecb1c9657ae5baf6cf7508c88c063ed3952c71b8a576ccef2f36ad6c44` |
| Sender (keyless)        | `0x8D1292274F64a2Cd6742Fe70f7b64E7AcB1a93ff`                         |
| Required sender balance | `300000000000000000` wei (0.3 MON, `gasLimit * gasPrice`)            |
| Factory address         | `0x53F970b36ec7C8Ade2954aCD7a16B2e5ba438dE4`                         |
| Runtime code hash       | `0x8001343f9a9c8c44b732426a862d7fd80899031f70ae3ef9f843aa49199aac21` |

The deployed runtime bytecode (216 bytes), with the factory address set in the immutable, is:

```txt
0x63dc61e1cd5f3560e01c0360ad576044356084356064356004356205a000831160ad5760806024350360ad5760a319601f8401601f191636030160ad577f00000000000000000000000053f970b36ec7c8ade2954acd7a16b2e5ba438de43014928360b9575b8060a45f375f85ae0290811560b157607848833b0202928391608e575b50505f5260205260405ff35b01340380609c575b82906082565b5f80808093335af11560ad575f6096565b5f80fd5b3d5f803e3d5ffd5b90335f5260205260405f209082850185811060ad573410156065575f80fd
```

To deploy the factory on a network where it is not yet present:

1. Check the code at the factory address. If its code hash equals the runtime code hash above, the factory is already deployed.
2. Transfer at least the required sender balance to the sender address.
3. Submit the signed transaction through an RPC endpoint that accepts transactions without a chain ID (for the reference RPC server, one started with `--allow-unprotected-txs`).

Anyone may perform these steps. The resulting deployment is identical regardless of who funds and submits the transaction.

## Rationale

### Yul Implementation

The factory contract must be implemented in Yul in order to use `verbatim` inline assembly, in the absence of compiler support in higher-level language compilers such as `solc`.

### Salt Binding

In direct calls, the factory is the deployer, so every caller shares the factory’s address space. Hashing the caller into the salt gives each caller its own address space, so that a deployment cannot be front-run: another caller submitting the same salt and initcode deploys to a different address.

The caller is hashed into the salt, rather than packed into a prefix of it, so that the salt passed to `CREATEBIG` retains its full 256 bits and its derivation is a single rule. `CALLER` is used rather than `ORIGIN`, so that contracts calling the factory cannot deploy to addresses reserved for the EOAs that call them.

### Delegated Call Mode

In a delegated call, the factory’s code executes as the calling contract, so `CREATEBIG` derives the new address from the caller, increments the caller’s nonce, and sets the constructor’s `msg.sender` to the caller. This gives contracts written in languages that cannot emit `CREATEBIG` exactly the semantics they would have if they executed it directly, including addresses that can be predicted from the caller’s own address.

The factory distinguishes the two modes by comparing `ADDRESS` with its own address, which the constructor stores as an immutable, following the pattern used by delegation-aware contracts such as OpenZeppelin’s `UUPSUpgradeable`. Detecting the mode, rather than offering a separate method for delegated calls, ensures that a direct call can never deploy with an unbound salt.

### Deterministic Deployment

A keyless deployment transaction gives the factory the same address on every Monad network without relying on any existing deployment infrastructure or on any party holding a key. Anyone can deploy the factory to a new network by funding the sender and submitting the transaction. The immutable holding the factory’s address is set by the constructor from `ADDRESS`, so the address does not appear in the initcode, and the transaction can be constructed without solving for a fixed point.

The gas limit and gas price are fixed by the signed transaction. The gas limit of 300,000 is approximately three times the gas used by the deployment under current pricing, leaving headroom for future repricing of contract creation. The gas price of 1,000 gwei is ten times Monad’s minimum base fee, so that the transaction remains includable under moderately elevated base fees, at a cost to the deployer of 0.3 MON.

### Refund Mechanism

In direct calls, the excess value is refunded with an ordinary `CALL`. The refund could instead be forced to the caller without executing its code, by creating an intermediate contract with the refund as its endowment and initcode that executes `SELFDESTRUCT` with the caller as beneficiary; this is not done because it adds code and gas to every refund, and makes the immutable factory depend on the future behavior of `SELFDESTRUCT`.

### No Deployment Event

The contract specified here follows the precedent of the widely used deterministic deployment proxy (by Arachnid), and does not emit a deployment event. In delegated calls, the factory’s code executes in the context of the calling contract, so any event would be emitted from the caller’s address under a signature that its ABI does not declare. Contract creations are already observable without an event, as tracers and indexers must recognize call frames created by `CREATEBIG` (see MIP-21), and the factory returns the deployed address and deposit to its caller.

## Backwards Compatibility

This MRC specifies a new application-layer contract, and does not modify the EVM, consensus or any existing contract.

The factory can be deployed on a network before MIP-21 is active there, as contract deployment does not validate opcodes. Until MIP-21 is active, every call to `deploy` that reaches `CREATEBIG` halts exceptionally, consuming all gas forwarded to it, as the extended opcode `0xAE 0x02` behaves like `INVALID` (MIP-7).

## Reference Implementation

The Yul source given in [Bytecode](#bytecode) is the reference implementation, and is provided as [`CreateBigFactory.yul`](../assets/MRC-22/CreateBigFactory.yul). The script [`nick.py`](../assets/MRC-22/nick.py) reproduces the deployment transaction, sender address and factory address given in [Deployment](#deployment) from the creation bytecode.

## Security Considerations

### Other Networks

The deployment transaction has no chain ID, and so can be included on any EVM network, not only Monad networks. On networks that do not implement MIP-21, the factory is inert: every call to `deploy` that reaches `CREATEBIG` halts exceptionally. Users must not assume that code at the factory address is usable on a given network without confirming that the network implements MIP-21.

### Simulation

RPC simulation that executes with `block.basefee` set to zero reports a deposit of zero, and the factory’s value check passes for any `maxDepositValue`. Callers that determine `maxDepositValue` or `msg.value` by simulation must simulate with a realistic base fee (see MIP-21).

### Memory Limit

The factory copies the initcode, up to 360KiB, into memory. Under the memory limit shared across call frames defined in [MIP-3](../MIPs/MIP-3.md), a call to the factory from deep within a call stack whose frames already hold large amounts of memory may exceed the limit, in which case the factory’s call frame halts exceptionally.

### Refund Re-entrancy

In direct calls, the factory returns any value in excess of the endowment and deposit to its caller with a `CALL` that forwards all remaining gas, which allows the caller to execute code. The factory holds no state, and the refund is its last action before returning, so a re-entrant call can only begin a new, independent deployment funded by its own `msg.value`, and cannot affect the deployment in progress.

If the refund call fails, the factory reverts, undoing the deployment. A contract that calls the factory directly must therefore be able to receive MON, or send exactly `value` plus the deposit so that no refund is made. Because the deposit depends on the base fee at inclusion, the latter is not generally practical; contracts that cannot receive MON should use delegated calls instead.

### Forced Balance

MON can be transferred to the factory without calling it, for example by `SELFDESTRUCT`. In direct calls, the factory requires `msg.value` to cover `value + maxDepositValue`, and computes the refund from `msg.value`, the endowment and the deposit alone, so the endowment, deposit and refund are always funded by the caller’s value and any other balance held by the factory is never spent. Such balance is permanently locked. In delegated calls, the factory’s balance is not involved.

### Deposit Funding

In direct calls, the deposit is funded only from the caller’s `msg.value`, bounded by `maxDepositValue`. In delegated calls, the endowment and deposit are drawn from the calling contract’s own balance, bounded by the `value` and `maxDepositValue` arguments it supplies; `msg.value` belongs to the calling contract’s own frame and is not checked by the factory. A contract that performs delegated deployments of caller-supplied initcode, with a `maxDepositValue` drawn from its own balance rather than from value supplied by its caller, allows callers to burn that balance (see MIP-21).

### Gas Retention

When the factory is the transaction’s top-level call, only the 1/64 of gas retained at `CREATEBIG` (EIP-150) is unavailable to the constructor. A contract that reaches the factory through `CALL` or `DELEGATECALL` loses a further 1/64 of its remaining gas, approximately 400,000 gas for a maximum-size deployment, which reduces the gas available for constructor execution (see MIP-21).

The refund in direct calls is paid from the gas retained by the factory and the gas returned by the constructor. If the constructor and deposit consume nearly all of the gas forwarded to them, and the retained 1/64 is less than the cost of a value-bearing `CALL`, the refund fails and the deployment reverts. Callers should supply gas with headroom above the deployment’s estimated cost.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
