---
mip: 24
title: SLH-DSA Verification Precompile
description: Add a precompile that verifies FIPS 205 SLH-DSA-SHA2-128s signatures
author: QEDK (@qedk)
discussions-to: https://forum.monad.xyz/c/mips/8
status: Draft
type: Standards Track
category: Core
created: 2026-11-13
---

## Abstract

This MIP adds one precompile, `VERIFY_SLHDSA_SHA2_128S`, that verifies SLH-DSA-SHA2-128s signatures as specified in FIPS 205. The input is `pubkey ++ signature ++ message` with no length fields: a 32-byte public key, a 7,856-byte signature, and a message of any length. The precompile verifies in pure mode with the empty context string and returns a 32-byte word: one for a valid signature, zero otherwise.

The precompile targets high-assurance keys such as account recovery and rotation keys, for examples ones held in FIPS 205 Hardware Security Models (HSMs).

## Motivation

Monad accounts and contracts authenticate with secp256k1 and, through the EIP-7951 precompile, secp256r1. Both rest on the elliptic-curve discrete logarithm problem, which a large enough quantum computer solves. Contracts have no protocol-level way to verify a post-quantum signature today.

SLH-DSA (FIPS 205) is the most conservative of the finalized post-quantum signature schemes: its security depends only on properties of the underlying hash function. It complements a lattice-based scheme and does not replace one. An account that signs routine transactions with a lattice key can register an SLH-DSA key for recovery and key rotation, so that a break of the lattice assumption does not cost it control of the account.

That role fits the scheme's cost profile. A public key is 32 bytes, one storage slot, while a signature is 7,856 bytes. The key is cheap to keep onchain and the signature is expensive to publish, which suits a key that signs relatively fewer times in the life of an account.

Verification is possible in contract code, but it is poorly suited for most chains:

- For this parameter set, a verifier makes about 2,123 hash calls on average and up to 3,823. Through the SHA-256 precompile each call costs at least 208 gas, which is about 443,000 gas on average and about 797,000 in the worst case, before memory and stack overhead. The precompile proposed here charges 36,000 gas for the same verification. Contract code pays 12 times that on average and 22 times in the worst case. Calldata costs the same on both paths and is left out of this comparison.

| Case | With precompile (gas) | Without precompile (gas) | Ratio |
| --- | --- | --- | --- |
| Excluding calldata, average | 36,000 | 443,055 | 12.3× |
| Excluding calldata, worst case | 36,000 | 796,684 | 22.1× |
| Including calldata, average | 336,520 | 590,263 | 1.75× |
| Including calldata, worst case | 336,520 | 943,892 | 2.80× |
- The gap is call overhead and not hashing. Of the 208 gas, 100 pays for the call and 60 is the base charge of the SHA-256 precompile, and a verifier pays both on every one of its calls. The proposed precompile charges 9.4 gas per hash call in the worst case, at a price set from measured verification time. Contract code therefore takes the block gas of 74 to 133 `ECRECOVER` calls for work that costs validators at most 5. That matters most in the event this scheme exists for: if the lattice assumption breaks, accounts would probably migrate to use keys backed by HSMs requiring a reasonably cheap signature verification pathway.
- The number of hash calls depends on the signature, so the gas a verification needs varies from one signature to the next. Monad charges the gas limit and not the gas used, so a caller that cannot simulate the exact signature in advance, such as a contract that forwards a fixed amount of gas, has to pay for the worst case.
- Hardware signers and key management services produce signatures exactly as FIPS 205 specifies. Variants that swap the standardized hash for `KECCAK256` (such as SPHINCS-) alter the standardized hash instantiation, parameters, or encoding.
- Consensus validates transactions before they are executed, so contract code cannot authenticate the sender of a transaction. A future transaction type with post-quantum authentication needs a verifier the protocol can run natively. This MIP specifies such a verifier and leaves the transaction type to a separate proposal.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119 and RFC 8174.

### Parameters

| Name | Value |
| --- | --- |
| `VERIFY_SLHDSA_SHA2_128S_PRECOMPILE_ADDRESS` | `0x0000000000000000000000000000000000001002` |
| `PK_LEN` | `32` |
| `SIG_LEN` | `7856` |
| `GAS_BASE` | `36000` |
| `GAS_PER_WORD` | `12` |

### Input

The input is a single byte string with no header and no length fields. Let `L` be its length in bytes.

| Field | Offset | Length |
| --- | --- | --- |
| `pubkey` | `0` | `PK_LEN` |
| `signature` | `PK_LEN` | `SIG_LEN` |
| `message` | `PK_LEN + SIG_LEN` | `L - PK_LEN - SIG_LEN` |

`pubkey` is the FIPS 205 public key encoding `PK.seed ++ PK.root`. `signature` is the FIPS 205 signature encoding `R ++ SIG_FORS ++ SIG_HT`. A message of length zero is permitted, so `L == PK_LEN + SIG_LEN` is a valid input.

### Verification

If `L < PK_LEN + SIG_LEN`, the result is failure.

Otherwise the result is success if and only if `slh_verify(message, signature, ctx, pubkey)` (FIPS 205, Algorithm 24) returns true, where:

- the parameter set is SLH-DSA-SHA2-128s (FIPS 205, Table 2);
- the hash functions are the SHA2 instantiation for security category 1 (FIPS 205, Section 11.2.1); and
- `ctx` is the empty string.

The precompile MUST NOT accept a context string and MUST NOT apply any pre-hash to the message. A signature produced under a non-empty context string, or by `hash_slh_sign` (FIPS 205, Algorithm 23), therefore fails verification.

The precompile MUST NOT validate `pubkey` beyond its length. FIPS 205 public-key validation requires only that the key be `2n` bytes long; no additional structural checks apply.

The result MUST depend only on the input bytes.

### Output

The precompile MUST return exactly 32 bytes: `0x0000000000000000000000000000000000000000000000000000000000000001` on success and `0x0000000000000000000000000000000000000000000000000000000000000000` on failure.

The precompile MUST NOT revert for any input. Running out of gas is the only way a call to it fails.

### Gas cost

```jsx
words = ceil(max(0, L - PK_LEN - SIG_LEN) / 32)
gas   = GAS_BASE + GAS_PER_WORD * words
```

The cost depends only on `L`. Implementations MUST charge it in full before performing any verification work. An input shorter than `PK_LEN + SIG_LEN` costs exactly `GAS_BASE`.

If the gas available to the call is less than the cost, the call fails and consumes all gas provided to it, as for other precompiles.

### Call semantics

The precompile is stateless. It MAY be invoked with `CALL`, `STATICCALL`, `DELEGATECALL` or `CALLCODE`, and MUST behave identically under each. As with the precompiles at `0x01` through `0x11`, a call that transfers value is permitted and does not affect the result.

The address MUST be included in the set of precompile addresses that are warm at the start of every transaction, as defined in EIP-2929.

An EIP-7702 delegation designator that points to the precompile address MUST be treated as a delegation to an account with empty code, as EIP-7702 specifies for precompiles.

### Chain Specifics

The precompile activates on each network at the timestamp set by the Hardfork Meta MIP that includes this proposal. Before activation, a call to the address behaves as a call to an account without code and returns empty returndata.

## Rationale

### Parameter set

FIPS 205 defines twelve parameter sets. This MIP adopts one, SLH-DSA-SHA2-128s, for three reasons.

- The small sets have the smallest signatures, and they verify faster than the fast sets, as RFC 9909 notes. Their cost is slow signing, which does not matter for a key that signs rarely. A signature is 7,856 bytes, against 17,088 for SLH-DSA-SHA2-128f.
- Security category 1 matches the level of the secp256k1 keys that accounts use today. The small sets at categories 3 and 5 have signatures of 16,224 and 29,792 bytes.
- The SHA2 and SHAKE sets have identical sizes. SHA-256 has hardware acceleration on every surveyed validator CPU, and the protocol already exposes it as a precompile. On that hardware a SHAKE variant costs 3.7 times the SHA2 variant, 132,000 gas against 36,000.

The SHAKE figure comes from pricing a hypothetical SLH-DSA-SHAKE-128s precompile by the rules of the gas schedule below, with 4-lane AVX2 Keccak-f[1600] and without AVX-512. Its worst case of 3,823 calls measures 318.3 µs on Zen 4, which is 12.63 times `ECRECOVER` and 75,773 gas at parity. Without AVX2, portable scalar Keccak takes 773.1 µs, which is 30.67 times `ECRECOVER` and 184,039 gas. An input found by an adversarial search of 2^30 tries per layer verifies in 259.7 µs, about 61,800 gas. These Zen 4 numbers come from a purpose-written AVX2 Keccak and not a tuned library, so they lean conservative.

On Zen 5 the worst case is estimated, not measured, at 84,000 to 107,000 gas. The 256-bit XOR, ANDN and shift instructions have the same throughput per cycle there as on Zen 4 and twice the latency, while `ECRECOVER` gets faster. `GAS_BASE` would be 132,000, which is 22 times `ECRECOVER` and, by the rule this MIP uses, the smallest multiple of `ECRECOVER` at least 20% above the top of that estimate. `GAS_PER_WORD` would be 15: Zen 4 parity is 11.43 gas per word, because AVX2 does not speed up single-stream SHAKE256, and the Zen 5 estimate is 10 to 13. If a SHAKE precompile is ever added at its own address, these are its starting constants.

### FIPS 205 without modification

Variants of SLH-DSA that use `KECCAK256` exist because the opcode is cheap inside the EVM. A precompile removes that reason. Verifying the published encoding without modification lets an account be backed by a key held in a hardware security module or key management service, which signs only as FIPS 205 specifies.

### One address per parameter set

The address verifies exactly one parameter set, so its input shape and gas cost are fixed and there is no selector byte to parse. Smaller parameter sets with a reduced signature limit (NIST SP 800-230 Initial Public Draft) have been proposed for standardization but are not final. If one is adopted later it can be given its own address without changing this one.

### Input layout

The layout `pubkey ++ signature ++ message` follows EIP-8355, which uses it for ML-DSA. Both fixed-size fields come first, so the message is the trailing bytes and no length field is needed. Using the same convention for both schemes lets a contract share its calling code between them.

### Pure mode and the empty context

FIPS 205 signs a message of any length, and the precompile accepts one. A caller that holds only a digest passes the digest as the message.

Pre-hash verification is a separate construction in FIPS 205 that binds the digest to the identifier of the hash function that produced it. Supporting it would require a second input format for no benefit to a caller that can supply the message.

The context string is fixed to empty because a context field would need a length prefix, and because the message a contract verifies is already a protocol-specific commitment. A caller that wants further domain separation includes it in the message.

### Fixed 32-byte output

`ECRECOVER` and `P256VERIFY` return empty returndata on failure, which is also what a call to an address without code returns. A contract deployed to several chains cannot then tell an invalid signature from a missing precompile. Returning 32 bytes in every case makes the two distinguishable: a returndata length other than 32 means the precompile is absent.

### Address

Low addresses are assigned by Ethereum, and the range from `0x100`, where `P256VERIFY` lives, is assigned by a separate process. Monad-specific precompiles start at `0x1000` with the staking precompile, followed by the reserve balance precompile of MIP-4 at `0x1001`.

Those two are stateful, dispatch on a Solidity selector, and accept `CALL` only. This precompile is stateless and takes raw bytes. Placing it at `0x1002` keeps it in Monad's range and is the next sequentially available address.

### Gas schedule

`GAS_BASE` prices the worst-case input on the surveyed validator hardware at parity with `ECRECOVER`, plus a margin. The Zen 4 figures below are measured. The Zen 5 figures are estimates built from published measurements, and the margin is sized to cover them.

A survey of 167 validator nodes found three CPU families.

| Family | Share | Models |
| --- | --- | --- |
| Zen 4 | 61% | Ryzen 7950X, 7950X3D, 8945HX, 8845HS; EPYC 4584PX, 4564P, 9474F, 9274F and others |
| Zen 5 | 37% | Ryzen 9950X, 9950X3D, 9900X; EPYC 4585PX, 4565P, 9555 |
| Zen 3 | 2% | Ryzen 5950X; EPYC 7313P |

`GAS_BASE` is derived as follows.

- Every surveyed CPU has SHA extensions (SHA-NI) and AVX2. The recommended deployment is bare metal, where no hypervisor can mask them, so the schedule assumes both. It does not assume AVX-512, which the Zen 3 CPUs lack.
- Verification makes at most 3,823 calls to the tweakable hash functions `F`, `H` and `T`, which is 7,712 SHA-256 compressions. Hashing an empty message into the digest adds 3, for 7,715. No input reaches this bound exactly, but inputs that come close can be searched for (see Security Considerations), so the schedule uses the bound and not the average of about 2,123 calls.
- An implementation that caches the compression of the constant first block needs 3,889 compressions for the same calls. The schedule assumes a verifier that uses SHA extensions and this optimization.
- The schedule does not assume interleaved SHA-256 streams. Interleaving is an optional optimization. On Zen 4 it lowers the worst case from 3.87 times `ECRECOVER` to 2.31 with two streams and 2.11 with four. On Zen 5 no more than two streams can help, and the estimate for two is 2.8 to 3.5 times.
- A client that hashes through OpenSSL one call at a time runs the worst case at 6.2 to 12.9 times `ECRECOVER` on Zen 4, which is up to 2.1 times below the priced rate. AVX2 does not help SHA-256 here, so the price depends on SHA extensions alone.
- The assumed verifier runs the worst case at 3.87 times `ECRECOVER` on Zen 4, which is 23,233 gas at Monad's `ECRECOVER` price of 6,000 gas. On Zen 5, the family with the highest ratio, it is estimated at 4.6 to 5.0 times, which is 27,700 to 29,900 gas. `GAS_BASE` is 6 times `ECRECOVER`, which is 36,000 gas. It is the smallest multiple of `ECRECOVER` at least 20% above the top of the Zen 5 estimate, and it is 55% above the Zen 4 measurement.

| Verifier | Source | × `ECRECOVER` | Parity gas |
| --- | --- | --- | --- |
| Reference port, OpenSSL EVP per call | Zen 4, measured | 12.86 | 77,159 |
| Reference port, OpenSSL `SHA256`, first block cached | Zen 4, measured | 6.23 | 37,359 |
| SHA-NI, single stream, first block cached | Zen 4, measured | 3.87 | 23,233 |
| SHA-NI, 2 interleaved streams | Zen 4, measured | 2.31 | 13,866 |
| SHA-NI, 4 interleaved streams | Zen 4, measured | 2.11 | 12,649 |
| AVX2 8-lane SHA-256, no SHA-NI | Zen 4, measured | 5.35 | 32,103 |
| Portable C, no SHA-NI, no SIMD | Zen 4, measured | 18.72 | 112,320 |
| OpenSSL scalar with SHA-NI masked | Zen 4, measured | 12.99 | 77,934 |
| SHA-NI, single stream, first block cached | Zen 5, estimated | 4.6 to 5.0 | 27,700 to 29,900 |
| SHA-NI, 2 interleaved streams | Zen 5, estimated | 2.8 to 3.5 | 16,900 to 20,700 |

The measured rows are from a Ryzen 9 7950X on bare metal, on one pinned core with 21 samples, and were repeated on a second core. Every row is the forced worst case of 3,823 calls. `ECRECOVER` is libsecp256k1 `ecdsa_recover` timed on the same core, where it takes about 25.2 µs, and parity gas is the ratio at 6,000 gas per `ECRECOVER`. The schedule prices the single-stream rows.

The Zen 5 rows are estimates and not measurements. No Zen 5 or Zen 3 machine has been benchmarked. The estimates rest on published figures.

- One SHA-256 stream is a dependency chain of 32 `SHA256RNDS2` instructions per block. The InstLatx64 timing dumps give that instruction a latency of 4 cycles on Zen 3, Zen 4 and Zen 5, so one stream costs about 128 cycles per block on each. A Ryzen 9 9950X3D is reported at 2.71 GB/s for single-stream SHA-256, against 2.51 GB/s on the measured 7950X. The 128-cycle figure was reproduced on an Emerald Rapids machine, where the latency is also 4 cycles.
- `ECRECOVER` is faster on Zen 5. Published libsecp256k1 verification times are 25.2 microseconds on a Ryzen 7950X and 19.6 on Zen 5, and the same dumps show 64-bit multiplication at 1.5 times the Zen 4 throughput. The low end of the single-stream estimate combines the 9950X3D throughput with the 19.6 microsecond figure. The high end scales the Zen 4 measurement by the `ECRECOVER` speedup alone.
- Zen 5 executes one `SHA256RNDS2` every 2 cycles, where Zen 4 executes one per cycle. Interleaving two streams raises raw SHA-256 throughput by 64% on a Ryzen 9950X and by 98% on Zen 4, as measured for a two-stream `sha256-ni` patch to the Linux kernel. The two-stream estimate applies that gain to the single-stream estimate, at the share of the raw gain that the Zen 4 verifier achieved.

Zen 3 has the same `SHA256RNDS2` timing as Zen 4 and a slower `ECRECOVER`, so its ratio is estimated at or below Zen 4's.

`GAS_PER_WORD` prices the single SHA-256 pass over the message and equals the per-word cost of the SHA-256 precompile. With SHA extensions on Zen 4 that pass measures 3.03 gas per word at parity.

### Intended use

The precompile makes verification cheaper than contract code and makes its cost fixed. It does not make the signature small. Publishing 7,888 nonzero calldata bytes contributes 315,520 gas to the calldata floor, producing a 336,520-gas floor including the transaction base cost. At the standard calldata rate the same transaction costs 147,208 gas before execution, so one that also pays `GAS_BASE` reaches 183,208 gas, which is below the floor. The verification charge is therefore absorbed by gas that the signature bytes already oblige the sender to buy, unless the rest of the execution exceeds about 153,000 gas. Actual costs depend on the zero-byte count, transaction encoding, and how the precompile input is assembled.

These costs are acceptable for recovery, key rotation and governance actions. They are not acceptable for routine transaction signing, for which a lattice-based scheme is the appropriate choice.

## Backwards Compatibility

This proposal adds a precompile at a previously unassigned address and does not modify existing behavior. Before activation a call to the address returns empty returndata, and afterwards it returns a 32-byte word. No deployed contract is known to depend on the prior behavior.

## Test Cases

The key pair for the first seven cases is generated with `slh_keygen_internal` (FIPS 205, Algorithm 18) from `SK.seed = 000102030405060708090a0b0c0d0e0f`, `SK.prf = 101112131415161718191a1b1c1d1e1f` and `PK.seed = 202122232425262728292a2b2c2d2e2f`. The resulting public key is `202122232425262728292a2b2c2d2e2f990ce6298792b128846a8e4a3a68954c`. Signatures are produced with `slh_sign` (FIPS 205, Algorithm 22) in its deterministic variant under the empty context.

The last two cases are taken from the NIST ACVP SLH-DSA signature verification vectors (revision FIPS205, test group 19).

| # | Case | Input length | Output | Gas | SHA-256 of input |
| --- | --- | --- | --- | --- | --- |
| 1 | Valid signature over the 32-byte message `00..1f` | 7920 | 1 | 36012 | `57312c2e507e62c0e92c520d0304853f120d5f8bfead0dd304fe73583d54f86a` |
| 2 | Valid signature over the empty message | 7888 | 1 | 36000 | `e223fb461334d492e8909760c4749b2dc8fa3fb5fdc93202c590b83d8a2e9bb2` |
| 3 | Valid signature over the 100-byte message `00..63` | 7988 | 1 | 36048 | `0689c12a59b06e154f24ebd3616f5aa510a6ae3ab17f95cfd31077f3adcc4ab5` |
| 4 | Case 1 with the lowest bit of the first signature byte flipped | 7920 | 0 | 36012 | `c3e30dfbc92e834ee43a7760c7d8143504a42151786b1789b07aed55378c2664` |
| 5 | Signature of case 1 with the message of case 3 | 7988 | 0 | 36048 | `0314914fb20143df1d1e1ba4a1fa09961b7dea954b88d57a367d90f0e2fea825` |
| 6 | Case 2 with the last byte removed | 7887 | 0 | 36000 | `44c33ff69c4e12e898054dc6a4882c99364e9b648612256dc288edcf3a9b7155` |
| 7 | Empty input | 0 | 0 | 36000 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 8 | ACVP `tcId` 255: empty context, modified `R` | 12608 | 0 | 37776 | `e39847ce2fe55dc865abdf6c5ce1a8864d5b7cc76a1df7725b23db66b3c6d606` |
| 9 | ACVP `tcId` 258: valid only under a 151-byte context | 15752 | 0 | 38952 | `19fed3885f023744d60a101c2a8005a06062e011a62103af568128c6434ed1ac` |

Cases 4 and 5 fail verification. Cases 6 and 7 are shorter than `PK_LEN + SIG_LEN`, so no verification is attempted. Case 9 verifies under the context string of the original vector and fails here because the precompile always uses the empty context.

## Reference Implementation

The following Python code block is a complete verifier for this parameter set. It reproduces the expected results of all 28 SLH-DSA-SHA2-128s vectors for the pure and internal interfaces in the NIST ACVP signature verification set, and of the test cases above.

```python
"""SLH-DSA-SHA2-128s verification (FIPS 205), pure mode, empty context."""
from hashlib import sha256

N, H, D, HP, A, K, LG_W, M = 16, 63, 7, 9, 12, 14, 4, 30
W, LEN1, LEN2 = 16, 32, 3
LEN = LEN1 + LEN2
PK_LEN, SIG_LEN = 2 * N, (1 + K * (1 + A) + H + D * LEN) * N
WOTS_HASH, WOTS_PK, TREE, FORS_TREE, FORS_ROOTS = 0, 1, 2, 3, 4

def adrs(layer, tree, typ, keypair=0, word2=0, word3=0):
    # Compressed address ADRSc (22 bytes), FIPS 205 section 11.2.
    return (layer.to_bytes(1, "big") + tree.to_bytes(8, "big") + typ.to_bytes(1, "big")
            + keypair.to_bytes(4, "big") + word2.to_bytes(4, "big") + word3.to_bytes(4, "big"))

def thash(pk_seed, adrs_c, data):
    # F, H and T_l for security category 1, FIPS 205 section 11.2.1.
    return sha256(pk_seed + bytes(64 - N) + adrs_c + data).digest()[:N]

def h_msg(r, pk_seed, pk_root, msg):
    inner = sha256(r + pk_seed + pk_root + msg).digest()
    seed, out, counter = r + pk_seed + inner, b"", 0
    while len(out) < M:  # MGF1-SHA-256
        out += sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return out[:M]

def base_2b(data, b, out_len):
    total = int.from_bytes(data, "big")
    bits = 8 * len(data)
    return [(total >> (bits - b * (i + 1))) & ((1 << b) - 1) for i in range(out_len)]

def climb(pk_seed, node, auth, idx, layer, tree, typ, keypair, base):
    # Shared Merkle path walk for FORS trees and XMSS trees.
    index = base + idx
    for j, sibling in enumerate(auth):
        index >>= 1
        pair = node + sibling if (idx >> j) & 1 == 0 else sibling + node
        node = thash(pk_seed, adrs(layer, tree, typ, keypair, j + 1, index), pair)
    return node

def fors_pk_from_sig(sig_fors, md, pk_seed, tree, keypair):
    roots = b""
    for i, idx in enumerate(base_2b(md, A, K)):
        part = sig_fors[i * (A + 1) * N:(i + 1) * (A + 1) * N]
        leaf = thash(pk_seed, adrs(0, tree, FORS_TREE, keypair, 0, (i << A) + idx), part[:N])
        auth = [part[N * (j + 1):N * (j + 2)] for j in range(A)]
        roots += climb(pk_seed, leaf, auth, idx, 0, tree, FORS_TREE, keypair, i << A)
    return thash(pk_seed, adrs(0, tree, FORS_ROOTS, keypair), roots)

def wots_pk_from_sig(sig, msg, pk_seed, layer, tree, keypair):
    digits = base_2b(msg, LG_W, LEN1)
    csum = sum(W - 1 - d for d in digits) << ((8 - (LEN2 * LG_W) % 8) % 8)
    digits += base_2b(csum.to_bytes((LEN2 * LG_W + 7) // 8, "big"), LG_W, LEN2)
    tips = b""
    for i, start in enumerate(digits):
        node = sig[i * N:(i + 1) * N]
        for j in range(start, W - 1):
            node = thash(pk_seed, adrs(layer, tree, WOTS_HASH, keypair, i, j), node)
        tips += node
    return thash(pk_seed, adrs(layer, tree, WOTS_PK, keypair), tips)

def slh_verify_internal(msg, sig, pk):
    if len(sig) != SIG_LEN or len(pk) != PK_LEN:
        return False
    pk_seed, pk_root = pk[:N], pk[N:]
    r, sig_fors, sig_ht = sig[:N], sig[N:N + K * (1 + A) * N], sig[N + K * (1 + A) * N:]
    digest = h_msg(r, pk_seed, pk_root, msg)
    md, tree_bytes, leaf_bytes = digest[:21], digest[21:28], digest[28:30]
    idx_tree = int.from_bytes(tree_bytes, "big") % (1 << (H - HP))
    idx_leaf = int.from_bytes(leaf_bytes, "big") % (1 << HP)
    node = fors_pk_from_sig(sig_fors, md, pk_seed, idx_tree, idx_leaf)
    for layer in range(D):
        xmss = sig_ht[layer * (LEN + HP) * N:(layer + 1) * (LEN + HP) * N]
        wots_pk = wots_pk_from_sig(xmss[:LEN * N], node, pk_seed, layer, idx_tree, idx_leaf)
        auth = [xmss[(LEN + j) * N:(LEN + j + 1) * N] for j in range(HP)]
        node = climb(pk_seed, wots_pk, auth, idx_leaf, layer, idx_tree, TREE, 0, 0)
        idx_leaf, idx_tree = idx_tree % (1 << HP), idx_tree >> HP
    return node == pk_root

def slh_verify(msg, sig, pk, ctx=b""):
    if len(ctx) > 255:
        return False
    return slh_verify_internal(b"\x00" + bytes([len(ctx)]) + ctx + msg, sig, pk)

def precompile(data):
    """Returns the 32-byte output of VERIFY_SLHDSA_SHA2_128S for the given input."""
    if len(data) < PK_LEN + SIG_LEN:
        return (0).to_bytes(32, "big")
    pk, sig, msg = data[:PK_LEN], data[PK_LEN:PK_LEN + SIG_LEN], data[PK_LEN + SIG_LEN:]
    return int(slh_verify(msg, sig, pk)).to_bytes(32, "big")
```

## Security Considerations

### Resource exhaustion

The gas cost is a function of the input length alone and is charged before verification starts, so a caller cannot obtain work without paying for it.

Verification work is bounded. For an input of valid length the precompile makes at most 3,823 tweakable hash calls plus one pass over the message, whether or not the signature is valid. The number of calls depends on the signature bytes, and a caller can search for inputs that approach the bound. Each layer's WOTS+ message is a hash of bytes the caller chooses, and about 2^40 hash evaluations per layer are enough to reach 3,298 calls, 86% of the bound. A measured search of 2^32 tries per layer reached 3,223 calls, 84% of the bound, and that input verifies in 43.9 µs on Zen 4 with four interleaved streams, which is 1.74 times `ECRECOVER` or about 10,450 gas at parity. `GAS_BASE` is therefore set for the bound and not for the average.

Benchmarking must include adversarially searched complete inputs and component benchmarks that exercise the maximum WOTS+ chain lengths. The gas schedule must then conservatively cover the analytical upper bound, including hashing, address construction, parsing, memory access, and dispatch overhead.

### Hardware assumption

The gas schedule assumes SHA extensions, which every surveyed validator CPU provides. Without them the best measured verifier on Zen 4 is 8-lane AVX2 SHA-256, at 5.35 times `ECRECOVER` or 32,103 gas at parity, which is within the price on Zen 4. Portable scalar code runs at 18.72 times `ECRECOVER`, 3.1 times below the priced rate. A node that falls back to such code executes this precompile below the priced rate.

The schedule also assumes a verifier that caches the first block (see Gas schedule). A client that hashes through OpenSSL one call at a time executes the worst case up to 2.1 times below the priced rate on Zen 4 even with SHA extensions. The factor is estimated to be larger on Zen 5, where `ECRECOVER` is faster and SHA-256 is not.

### Domain separation

The precompile verifies under the empty context string and provides no application-specific domain separation. As with `ECRECOVER`, the scheme signs the bytes it is given. Binding to a chain, a contract, a nonce or an intent has to be built into the message by the caller. A key that is also used outside Monad under the empty context can have its signatures replayed here unless the message format prevents it.

### Signature bytes are not identifiers

Callers should not use signature bytes as a unique identifier or nullifier for a message. Replay protection belongs in the message, for example as a nonce.

### Security level

SLH-DSA-SHA2-128s targets NIST security category 1. Its security rests on SHA-256 and does not depend on any number-theoretic or lattice assumption. The parameter set is designed for up to 2^64 signatures per key, far more than a recovery key produces.

### Signer-side risks

FIPS 205 makes hedged signing the default and permits a deterministic variant. Deterministic signing is more exposed to fault attacks on the signing device. This is outside the control of the precompile, but wallet and custody implementers should prefer hedged signing.

### Implementation

Verification handles only public data, so it needs no constant-time guarantees. Clients should use a maintained implementation and validate it against the NIST ACVP vectors and the cases in this document.

### Scope

Activating the precompile does not make any account quantum-resistant. An account stays controlled by its secp256k1 key until the protocol or the account's own code removes that key's authority, which this MIP does not address.

## Open Questions

### Gas constants

`GAS_BASE` rests on measurements from one Zen 4 machine and on an estimate for Zen 5, which has the highest ratio and has not been benchmarked. A measurement on Zen 5 hardware, with the forced worst case and adversarially searched inputs against the verifier the client uses, would replace the estimate. A lower price requires interleaving to become an assumption of the schedule. With two streams parity is 13,866 gas on Zen 4 and an estimated 16,900 to 20,700 on Zen 5, which by the same rule would give 30,000 gas.

### Further parameter sets

Parameter sets with a reduced signature limit have been proposed and would roughly halve the signature size. Whether to add one at an adjacent address once it is final is open.

### Lattice companion

This precompile is designed as the cold-path complement to a lattice-based verifier, such as the ML-DSA precompiles of EIP-8355. Whether the two should activate in the same network upgrade is open.

### Native transaction authentication

How a future transaction type refers to this verifier, and how it prices the 7,856 signature bytes it would carry, is left to that proposal.

## Copyright

Copyright and related rights waived via CC0.
