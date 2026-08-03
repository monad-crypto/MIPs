---
mip: 14
title: Account Attestation Registry
description: An on-chain registry where an account publishes self-attestations about itself, authorized by proof-of-control
author: Mohsen Ahmadvand (@mr-ma)
discussions-to: <forum-thread>
status: Draft
type: Standards Track
category: MRC
created: 2026-07-21
---

## Abstract

This MRC defines an on-chain registry where an account can publish facts about itself that the chain does not otherwise show, for example the key-management scheme behind the address (MPC, TSS, a TEE-held key, or an off-chain multisig) or who operates it. Only the account can write its own entries, and it proves that by writing from the address it controls.

Each entry is stored under a topic the account chooses, kept exactly as written (by convention a small JSON object) and never interpreted by the registry, so the registry fixes no list of topics and judges no claim. Any service that needs to know something about an address it cannot read from the chain (a risk dashboard, a wallet or custodian directory, a validator explorer, a compliance tool) can read these entries directly, without a separate identity system.

## Motivation

Many onchain accounts present as a plain externally-owned account: one address, no code, controlled by one key. On-chain, that is all they ever appear to be. In practice the single address is often the front for a key-management scheme that produces one ordinary signature yet is invisible on-chain:

- an MPC wallet, where the key is split across parties and never reconstructed;
- a TSS (threshold-signature) wallet, where an m-of-n quorum jointly produces one signature;
- a key held inside a TEE, an attested secure enclave;
- an off-chain multisig, where an m-of-n approval is coordinated off-chain and settled as a single signature.

Each produces a standard ECDSA signature that encodes none of this structure, so the address is byte-for-byte indistinguishable from a single-key EOA. None of the backing is observable from outside: there is no code to inspect, and the quorum, enclave, or approval policy leaves no on-chain trace. The strongest fact provable on-chain is control of the address itself, demonstrated trivially by signing or transacting from it.

This registry keys writes to the address itself: because the writer is always the subject, a write needs only a local `msg.sender` check with no external identity lookup, which keeps the contract minimal and reusable by any service.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Overview

Compliant implementations MUST deploy a single contract that conforms to the `IAccountRegistry` interface below and expose `string public constant VERSION = "MRC-14/1.0.0"`. Every metadata entry is identified by a `metadataId` derived from its subject; the contract MUST authorize each write against the subject account (see [Authorization](#authorization)). The contract exposes a write method and read methods for the stored metadata.

### Metadata identity

Metadata entries are keyed by the account and the fact the entry is about:

```
metadataId = keccak256(abi.encode(account, topic, index))
```

- `account`: the subject address, i.e. the account the metadata makes claims about and the only party authorized to write it.
- `topic`: a service-defined label for what the entry covers (e.g. `"custody"`, `"operator"`, `"security-contact"`). The registry treats it as an opaque string.
- `index`: distinguishes multiple entries under the same `(account, topic)`, e.g. successive dated attestations. It MUST be `0` for single-valued topics.

### Interface

```solidity
interface IAccountRegistry {
    /// The subject an entry is keyed to: `(account, topic, index)`. See
    /// Metadata identity.
    struct Subject {
        address account;
        string  topic;
        uint256 index;
    }

    /// Emitted on every write. `topicKey` is `keccak256(bytes(topic))`,
    /// indexed for `(account, topic)` filtering. See Events.
    event MetadataUpdated(bytes32 indexed metadataId, address indexed account, bytes32 indexed topicKey, string topic, uint256 index);

    /// MUST return "MRC-14/1.0.0".
    function VERSION() external view returns (string memory);
    /// Pure derivation of the metadata id for a subject.
    function metadataId(Subject calldata subject) external pure returns (bytes32);

    /// Set or replace a subject's entry. `data` is stored verbatim. See
    /// Authorization, Write Preconditions, and Field Semantics.
    function setMetadata(Subject calldata subject, string calldata data) external;

    /// Read the entry's `data` for `subject`, or the empty string if none exists.
    function getMetadata(Subject calldata subject) external view returns (string memory data);
    /// True iff a metadata entry has been written for `subject` (its `data` is non-empty).
    function hasMetadata(Subject calldata subject) external view returns (bool);
}
```

### Authorization

Authority over a metadata entry is the subject account itself. A write MUST be gated by `msg.sender == subject.account`. This is the proof-of-control the trust model rests on: only the party that controls the address may state facts about it.

The check is a single equality against `msg.sender`, which holds whether the account is an EOA that signs the transaction itself or a contract account that executes the write from its own context. For an MPC, TSS, or off-chain-multisig account the quorum's own signing ceremony produces that call, so the multi-party structure is accommodated with no delegation primitive. Because the subject is always the account, no ownership or admin model and no external contract call is needed to establish authority. The revert reason for unauthorized callers is implementation-defined but SHOULD be a custom error (e.g. `Unauthorized()`).

### Field Semantics

- `data` SHOULD be a UTF-8 JSON object whose keys are the topic's fields. A service defines its own schema and MAY include auxiliary values (evidence or document URIs, content hashes, signed attestations, or payloads defined by a later MRC) under its own keys; this MRC defines no schema and reserves no keys.
- The registry MUST NOT validate or parse `data`, MUST NOT reject syntactically invalid JSON, and MUST return it byte-for-byte on read. JSON conformance is a convention enforced by writers and consumers, not by the registry.

### Write Preconditions

`setMetadata` MUST revert when `data` or `topic` is empty. A stored entry is therefore always non-empty, so `hasMetadata(subject)` is `true` exactly for a subject that `setMetadata` has written. To correct or retract an attestation the account overwrites `data` with a new value; this MRC defines no separate deletion function.

### Events

Exactly one `MetadataUpdated` MUST be emitted on every successful `setMetadata`, signalling that the metadata entry for `metadataId` changed. The event carries the entry's `topic` and `index` but not its `data`; a consumer reads the contents via `getMetadata`, which MUST return the entry as of that write. Because `metadataId` is a one-way hash of `(account, topic, index)`, emitting `topic` and `index` lets a consumer reconstruct the full subject of the changed entry directly from the log, with no need to brute-force `metadataId` over candidate indices.

The event indexes `metadataId`, `account`, and `topicKey` (= `keccak256(bytes(topic))`), the three indexed topics the EVM permits besides the event signature. Indexing `account` lets a consumer stream every change for an address; indexing `topicKey` lets it filter by `(account, topic)` without scanning unrelated entries.

### Read Semantics

- `getMetadata` and `hasMetadata` MUST NOT call any external contract.
- `getMetadata(subject)` MUST return the stored `data` for `subject`, or the empty string if no entry exists.
- `hasMetadata(subject)` MUST return `true` iff a metadata entry has been written for `subject` (its stored `data` is non-empty).
- `VERSION()` MUST return `"MRC-14/1.0.0"`.
- Implementations MAY expose additional view functions but MUST NOT alter the semantics of any function defined here.

### Example topics

The registry defines no topics; the following are illustrative conventions a consuming service might adopt. They are non-normative. A service publishes its own field schema for each topic, and the registry stores whatever is written.

| topic (example) | `data` keys (example) |
|---|---|
| `custody` | scheme (mpc / tss / tee / offchain-multisig), threshold(m,n), provider, attestationUri |
| `operator` | operator, identityDisclosed, affiliation, proofUri |
| `security-contact` | contactUri, disclosurePolicy |

### Chain Specifics

A registry contract conforming to this MRC is deployed at an ordinary contract address chosen at deployment time. It depends on no precompile: authority for every subject is the account address itself, checked by an equality against `msg.sender`, with no external call. A conformant registry functions on any Monad-EVM network. This MRC defines an interface and a behavioural spec, not a specific bytecode or address. Independently-deployed conformant implementations may coexist, and integrators choose which to write to and read from.

## Rationale

**Why key metadata by the account address?** The address is the one identity an account can prove control of on-chain, so it is the only anchor that needs no second identity system. A reader resolves every attestation against an address it already tracks.

**Why `(account, topic, index)`?** `topic` partitions the distinct facts an account may state about itself; `index` lets the account keep multiple entries under the same `(account, topic)` (for example a sequence of dated attestations), each with its own `metadataId`, so assigning a fresh index does not overwrite earlier ones. The registry does not enforce append-only or index monotonicity; keeping past entries immutable is a convention, not an on-chain guarantee. Single-valued topics simply use `index = 0`.

**Why a single JSON `data` object instead of typed struct members?** The set of facts differs by service and evolves over time. A JSON object keeps the registry stable across those changes with no ABI break or storage migration. The entries also have no first-class human-readable fields (name, logo) that would justify dedicated on-chain columns.

**Why proof-of-control as the authority?** An MPC, TSS, TEE, or off-chain-multisig backing produces a standard ECDSA signature that encodes none of its structure, so the signing address is the strongest authority observable on-chain. Re-deriving identity any other way would introduce a divergent identity system that a reader would have to trust separately.

**Why is every value self-reported and never authoritative?** A `data` value is a self-reported statement, not a proof. A consumer must be free to grade it against any supporting evidence and against independent observation; the registry stating it does not make it true.

**Prior art / alternatives considered.** Several existing designs cover adjacent ground, and this MRC deliberately diverges from each:

- **ERC-780 (Ethereum Claims Registry)** keys every claim by `(issuer, subject, key)`. It does support self-attestation (`setSelfClaim`), but even a self-claim stores the issuer in the key (`registry[issuer][subject][key]`), so the issuer dimension is always present. This MRC has no issuer dimension: an entry is keyed by the subject alone, and authority is proof-of-control of that address.
- **EAS (Ethereum Attestation Service)** is a general attestation layer with an on-chain schema registry, arbitrary attester→recipient attestations, resolver hooks, and revocation. This MRC is intentionally narrower: no schema registry (the single `data` field is an opaque, unparsed convention), no attester/recipient split (the subject is always the writer), and no resolver extension points. The "why not just use EAS" answer is that a consumer here depends only on the chain and the account's own statements, not on a schema registry or an attester graph, which keeps the contract small enough to be reused by any service.
- **ENS text records** store key→value strings under a *name*, resolving identity through the ENS namespace and its ownership model. This MRC keys metadata directly on the account address, the one identity provable on-chain without a name-resolution system, so a reader resolves attestations against an address it already tracks.

The common thread is that authority in this MRC is proof-of-control of the subject address (not an issuer, attester, or name owner), and it carries no schema registry and no external identity resolution, which is what keeps the contract minimal and reusable.

## Backwards Compatibility

This MRC is purely additive: it specifies a new application-layer contract and changes no precompile, EVM, or consensus behaviour. Tools that consume off-chain metadata MAY continue to do so, and SHOULD use off-chain sources for accounts that have not yet filed and to corroborate the self-attestations of those that have.

## Test Cases

1. `setMetadata` from the subject account succeeds, persists `data` (readable via `getMetadata`), and emits `MetadataUpdated`.
2. `setMetadata` from a caller other than the subject account reverts.
3. `setMetadata` with empty `data` reverts.
4. `setMetadata` stores `data` verbatim, with no JSON validation by the registry.
5. A second `setMetadata` for the same subject overwrites `data` and emits `MetadataUpdated`.
6. Metadata entries under the same account with different `(topic, index)` are independent: a write to one changes neither the `metadataId` nor the contents of another.
7. `hasMetadata(subject)` returns `false` for a subject with no entry and `true` after a successful `setMetadata`.
8. `VERSION()` returns `"MRC-14/1.0.0"`.
9. `setMetadata` with an empty `topic` reverts.

## Reference Implementation

The normative artifact of this MRC is the interface and behavioural spec in [§ Specification](#specification); no bytecode is mandated by this document.

## Security Considerations

Every value is a self-attestation authorized only by control of the subject address, not a proof of the fact it asserts. A consumer MUST treat each value as a claim, weigh it against off-chain evidence, and MUST NOT render it as verified fact or let it override anything observable on-chain. Whoever controls the account's key can change its metadata unilaterally, so the integrity of an entry rests on that account's own key-security assumptions.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
