---
mip: 13
title: Validator Metadata Registry
description: An on-chain registry standard for human-readable Monad validator metadata
author: Dorde Mijovic <dorde@monad.foundation> (@mijovic), Jackson Lewis <jlewis@monad.foundation>
discussions-to: 
status: Draft
type: Standards Track
category: MRC
created: 2026-06-15
---

## Abstract

This MRC specifies an on-chain registry contract that augments the Monad staking precompile (at `0x0000000000000000000000000000000000001000`) with human-readable validator metadata: name, website, description, logo URL, a JSON `socials` field, and a JSON `additionalInfo` field for forward-compatible extensions. At minimum, a validator's own authority address — as reported by the staking precompile — MUST be able to write metadata for that validator; implementations are free to grant write access to additional callers under their own authorization model. The registry exposes both full-record writes and per-field updates, plus read methods for the stored record.

## Motivation

The Monad staking precompile is the source of truth for validator identity at the consensus layer, but it intentionally exposes only the data required for consensus and reward accounting (authority address, flags, stake, commission, public keys, etc.). It does not provide any human-readable identity for a validator.

Wallets, block explorers, staking dashboards, governance UIs, and delegation tools all need to render validators by a recognizable name and logo rather than by a numeric `validatorId`. Today each integrator solves this independently — typically by maintaining an off-chain `metadata.json` file or a centrally-curated list — which produces inconsistent naming across the ecosystem, broken or stale links, and a centralization risk where one curator gates how validators are labeled to users.

A permissionless, validator-controlled on-chain registry eliminates the curation bottleneck: the same authority key that already controls staking parameters is the one allowed to publish a validator's metadata, and any integrator can read it directly from a registry contract conforming to this standard.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Overview

Compliant implementations MUST deploy a single contract that conforms to the `IValidatorMetadata` interface defined below. The contract MUST query the Monad staking precompile at `0x0000000000000000000000000000000000001000` to determine the current authority address of any given `validatorId`, and MUST accept write calls from that authority address at the time of the call. Implementations MAY additionally accept writes from other callers under their own authorization rules; see [Authorization](#authorization).

### Interface

```solidity
interface IValidatorMetadata {
    /// Emitted on every successful write to a validator's metadata.
    event MetadataUpdated(uint64 indexed validatorId, address indexed authority, Metadata metadata);

    /// Validator metadata record. See Field Semantics for write rules and the JSON
    /// conventions for the `socials` and `additionalInfo` fields.
    struct Metadata {
        string name;
        string website;
        string description;
        string logo;
        string socials;
        string additionalInfo;
    }

    /// Field selector for `updateMetadataField`.
    enum Field {
        NAME,
        WEBSITE,
        DESCRIPTION,
        LOGO,
        SOCIALS,
        ADDITIONAL_INFO
    }

    /// Address of the Monad staking precompile used for authority resolution.
    /// Implementations MUST return `0x0000000000000000000000000000000000001000`.
    function STAKING_PRECOMPILE() external view returns (address);

    /// Set or replace the full metadata record for a validator. Authorized callers
    /// and revert conditions are defined in Authorization and Field Semantics.
    function setMetadata(uint64 validatorId, Metadata calldata metadata) external;

    /// Update a single field, leaving other fields untouched. Reverts if no record
    /// exists yet for `validatorId` — `setMetadata` is the only entry point that may
    /// create a record. For `field == SOCIALS` or `ADDITIONAL_INFO`, callers SHOULD
    /// pass a UTF-8 JSON object; the registry stores `value` verbatim.
    function updateMetadataField(uint64 validatorId, Field field, string calldata value) external;

    /// Read the full stored metadata record for `validatorId`, or an all-default
    /// `Metadata` struct if no record exists. Use `hasMetadata` to disambiguate.
    function getMetadata(uint64 validatorId) external view returns (Metadata memory metadata);

    /// True iff a metadata record has been written for `validatorId`. Equivalent to
    /// the stored `name` being non-empty, since `name` is required on every write.
    function hasMetadata(uint64 validatorId) external view returns (bool);

    /// Read just the validator's stored name, or the empty string if no metadata is set.
    function getValidatorName(uint64 validatorId) external view returns (string memory);
}
```

### Authorization

For every write entry point (`setMetadata`, `updateMetadataField`), implementations MUST resolve the validator's authority by calling `getValidator(validatorId).authority` on the staking precompile at `STAKING_PRECOMPILE()` at the time of the call, and MUST accept the call when `msg.sender` equals that address. Implementations MUST NOT cache or shadow the authority address: a change of authority in the staking precompile MUST take effect immediately.

Beyond this baseline, implementations are free to define their own authorization model and MAY accept writes from additional callers — for example, a delegated operator key, a multisig wrapper, a governance contract, or a designated metadata manager — provided that any caller not granted access under the chosen scheme is rejected. The revert reason for unauthorized callers is implementation-defined but SHOULD be a custom error (e.g. `Unauthorized()`) rather than a string.

### Field Semantics

- `name` is REQUIRED and MUST be non-empty for any validator that has any metadata at all. `setMetadata` MUST revert when given an empty `name`. `updateMetadataField` MUST revert when called with `Field.NAME` and an empty value. As above, the revert reason is implementation-defined but SHOULD be a custom error (e.g. `ValidatorNameEmpty()`).
- `website`, `description`, `logo`, `socials`, and `additionalInfo` are OPTIONAL strings. The registry MUST NOT validate their content; integrators SHOULD treat them as untrusted input and sanitize before rendering.
- `socials`, when non-empty, SHOULD be a UTF-8 JSON object whose keys are lowercase platform identifiers and whose values are the corresponding profile URLs or handles, for example:

  ```json
  {
    "x": "https://x.com/monad_xyz",
    "telegram": "https://t.me/monad",
    "discord": "https://discord.gg/monad",
    "github": "https://github.com/monad-developers"
  }
  ```

  The set of platform keys is not enumerated by this MRC — integrators SHOULD treat unknown keys as opaque and pass them through. Encoding socials as a JSON object (rather than naming individual social platforms in the struct) keeps the registry usable as the ecosystem's social-media landscape shifts over time.
- `additionalInfo`, when non-empty, SHOULD be a UTF-8 JSON object. It is reserved for forward-compatible metadata extensions (e.g. delegation policies, signed attestations, content hashes, future MRC payloads) and has no top-level schema defined by this MRC; downstream MRCs MAY define reserved key namespaces inside it.
- Both `socials` and `additionalInfo` are stored as raw strings. The registry MUST NOT attempt to parse them, MUST NOT reject syntactically invalid JSON, and MUST return them byte-for-byte on read. JSON conformance is therefore a convention enforced by writers and consumers, not by the registry.

### Write Preconditions

`setMetadata` is the only entry point that may create a new record. `updateMetadataField` MUST revert when invoked for a `validatorId` that has no existing record (i.e. one for which `hasMetadata(validatorId)` is `false`). This invariant is what makes the "`name` is REQUIRED" rule enforceable: a record can never exist with an empty `name`, because the only way to create one — `setMetadata` — rejects empty names, and field updates cannot run before a record exists.

### Events

Exactly one `MetadataUpdated` event MUST be emitted on every successful write. The `metadata` field MUST reflect the complete record as observable immediately after the write — for `updateMetadataField` this means the previously stored fields plus the newly updated one.

### Read Semantics

- `getMetadata`, `getValidatorName`, and `hasMetadata` MUST NOT call the staking precompile.
- `STAKING_PRECOMPILE()` MUST return `0x0000000000000000000000000000000000001000`.
- `hasMetadata` MUST return `true` iff the stored `name` is non-empty. Because `name` cannot be set to the empty string except as part of an all-default uninitialised slot, this is equivalent to "any metadata has ever been written for this validator and not subsequently nulled".
- Implementations MAY expose additional view functions outside this interface (e.g. a combined "staking info + metadata" reader), but MUST NOT alter the semantics of any function defined here.

### Chain Specifics

A registry contract conforming to this MRC is deployed at an ordinary contract address chosen at deployment time — not at the precompile address — and the two are unrelated other than that the registry calls into the precompile at `0x0000000000000000000000000000000000001000` for authority resolution.

This MRC defines an interface and a behavioural spec, not a specific bytecode or address. Any number of independently-deployed conformant implementations may coexist on any Monad-EVM network; this MRC does not designate any of them as canonical and does not record an address. Integrators and validators choose which conformant deployment(s) to write to and read from on the basis of their own trust and operational preferences.

Any deployment is valid only on networks that expose the staking precompile at `0x0000000000000000000000000000000000001000`; on networks where the precompile is absent, write methods would revert and read methods that proxy through the precompile would return the zero record, so a conformant registry cannot function on such networks.

## Rationale

**Why anchor authorization to the staking precompile?** The precompile already holds the canonical mapping from `validatorId` to authority address and is the only mechanism by which authority rotations are recognized by consensus. Re-deriving identity from any other source (e.g. an ECDSA signature over a name) would introduce a second, divergent identity system.

**Why separate `setMetadata` from `updateMetadataField`?** A validator that only wishes to change, say, a logo URL would otherwise have to resubmit the entire record (including potentially long `description` and `additionalInfo` fields) just to mutate one short string. Per-field updates reduce gas and calldata costs and reduce the chance of an authority accidentally clobbering other fields.

**Why is `name` the only required field?** A validator without a name is indistinguishable from an unset record (see `hasMetadata`). All other fields have defensible empty defaults — a validator may legitimately have no website, no logo, or no social presence.

**Why a JSON `additionalInfo` field?** Extending the struct is an ABI- breaking change. A free-form text field lets future MRCs layer structured extensions (delegation policies, signed attestations, IPFS CIDs, etc.) without a new registry deployment or storage migration. JSON was chosen over an opaque `bytes` blob because the rest of the record is already human-readable text, every off-chain consumer in this space already speaks JSON, and binary payloads can be hex-encoded inside a JSON value the few times they're needed.

**Why JSON for `socials` (instead of one column per platform)?** Naming specific platforms in the struct would lock the registry to today's social-media landscape. A JSON object keyed by platform identifier is structured enough that tooling can pick out a known key (`"x"`, `"telegram"`, …) without prescribing the set; new platforms can be added by validators without any change to the registry, and platforms can be dropped without leaving dead struct fields behind. The registry deliberately does not parse JSON — that would be expensive on-chain and would force the spec to pin a specific JSON dialect — so conformance is enforced socially at the writer and reader.

**Why is the authority address only a baseline, not the sole writer?** The authority address is the one identity that every validator demonstrably controls today, so anchoring on it gives a consistent, consensus-aligned default. But validators have real reasons to delegate metadata management — hot-key/cold-key separation, team operators rotating the brand without touching the staking key, multisig-gated changes for security-conscious operators — and forcing those flows to share the authority key would either expand its blast radius or push validators into off-chain curation again. Letting implementations extend the writer set above the authority baseline preserves the auditability of the default path (anyone can verify the authority is at least permitted) while leaving room for operationally realistic policies on top.

**Why store data on-chain rather than just a content hash?** Storing names on-chain is cheap relative to the gas budget of validators, removes a dependence on external content-addressed storage availability for first-class fields like name and website, and lets light integrators read metadata without running an IPFS or HTTP fetcher. Heavier extension payloads MAY use `additionalInfo` to hold a content hash.

## Backwards Compatibility

This MRC is purely additive: it specifies a new application-layer contract and does not change the staking precompile, the EVM, or any existing consensus or networking behaviour. It introduces no backwards-incompatible changes.

Ecosystem tools that currently consume off-chain `metadata.json` files MAY continue to do so. Tools SHOULD migrate to reading from the registry when available, treating off-chain files as a fallback for validators that have not yet registered metadata.

## Test Cases

Conformant implementations are expected to demonstrate the following behaviours:

1. A call to `setMetadata` from the validator's authority succeeds, persists the full record, and emits `MetadataUpdated` with the stored record.
2. A call to `setMetadata` from an address that is neither the validator's current authority nor authorized under the implementation's own scheme reverts.
3. A call to `setMetadata` with `metadata.name == ""` reverts, even if every other field is non-empty and the caller is authorized.
4. A call to `updateMetadataField` against a `validatorId` for which `hasMetadata` is `false` reverts, regardless of the calling address.
5. A call to `updateMetadataField` for each `Field` variant updates only that field, leaves all other fields unchanged, and emits `MetadataUpdated` carrying the full post-update record.
6. A call to `updateMetadataField(_, NAME, "")` reverts. Calls with any other `field` and an empty `value` succeed and clear that field.
7. A call to `updateMetadataField(_, ADDITIONAL_INFO, value)` stores `value` verbatim into `additionalInfo`, with no JSON validation performed by the registry.
8. After the staking precompile's authority for a validator rotates from `A` to `B`, a write from `B` succeeds without requiring any action against the registry, demonstrating that authority is resolved live.
9. `hasMetadata(id)` returns `false` for any `id` that has never been written, and `true` after a successful `setMetadata`.
10. `STAKING_PRECOMPILE()` returns `0x0000000000000000000000000000000000001000`.

## Reference Implementation

The normative artifact of this MRC is the interface and behavioural spec in [§ Specification](#specification); no bytecode is mandated by this document.

## Security Considerations

**Authority key compromise:** A compromised authority key can both drain validator stake (via the staking precompile) and post arbitrary metadata (via this registry). The registry does not amplify the impact of a compromise beyond what the staking precompile already allows. Validators SHOULD protect the authority key accordingly and SHOULD treat rotation of the authority as the canonical recovery path.

**Phishing and impersonation via metadata:** Because `name`, `website`, `logo`, and `socials` are free-form and unverified, a malicious validator may copy the branding of another validator to siphon delegations. Integrators displaying registry data SHOULD:

- Always render `validatorId` and the validator's authority address alongside human-readable fields, so that two distinct validators with identical names remain distinguishable.
- Treat all string fields as untrusted: HTML-escape on render, refuse to auto-load remote images by default, and validate URL schemes.
- Consider maintaining a curated allow-list of authority addresses for any feature that grants elevated trust (e.g. featured validators) — the registry's job is to provide self-attested data, not to attest its truth.

**Storage griefing:** Strings and `additionalInfo` are unbounded in length. A validator may pay to store an arbitrarily large record. This affects only that validator's own gas cost (an authorized caller must sign the transaction) and the SLOAD cost of `getMetadata` for that validator. Implementations that grant write access beyond the authority address SHOULD ensure the additional callers cannot impose costs the validator did not themselves agree to bear. Integrators concerned about read gas SHOULD prefer the field-scoped getters (`getValidatorName`, `hasMetadata`) where they suffice, and SHOULD impose their own client-side display limits on string lengths.

**Authority resolution race:** Authorization is resolved by calling the staking precompile inside the same transaction as the write. There is no TOCTOU window: the precompile cannot change authority mid-transaction.

**Reorgs:** Like any on-chain state, registry contents are subject to reorganisation. Integrators that cache the registry SHOULD respect the chain's finality guarantees before treating an update as durable.

**`STATICCALL` and `DELEGATECALL` restrictions:** Monad's staking precompile permits only standard `CALL`s. The registry MUST invoke the precompile via ordinary `CALL` (no `delegatecall`, no `staticcall` on write paths). View methods that proxy to the precompile MUST be marked `view`, which forces `STATICCALL` semantics — implementations relying on this MUST verify the precompile's view methods are STATICCALL-compatible on the target network.

**No upgrade path:** This MRC specifies an immutable, non-upgradeable contract. A future MRC that changes the storage layout or interface MUST take effect through new deployments at new addresses, not by mutating existing ones. Integrators MUST treat each registry deployment as fixed and independently track which deployment(s) they consider current, rather than assume the standard guarantees a stable address over time.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
