---
mip: 10
title: Deterministic RaptorCast 
description: Introduces a canonical encoding scheme for RaptorCast that closes asymmetric liveness and equivocation attack surfaces and reduces dissemination latency
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-10-deterministic-raptorcast/453
status: Draft
type: Standards Track
category: Core
created: 2026-04-28
---

## Abstract

This MIP proposes Deterministic RaptorCast (v1), a new broadcast mode for the RaptorCast dissemination layer that fixes the Raptor encoding via a publicly derivable seed and enforces per-round equivocation detection by recording the first valid (Merkle root, leader signature) pair seen for each round, referred to as an ``EncodingCommitment``.

The change delivers three benefits: (1) it can enable validators to vote directly on the Merkle root commitment upon receiving a verified chunk without decoding, saving one message delay on the critical path; (2) it closes asymmetric liveness attacks in which a Byzantine leader selectively withholds singleton Encoding Symbol Identifiers (ESIs) from targeted validators, causing reconstruction delays of several hundred milliseconds; and (3) it closes mixed-commitment equivocation, in which a leader constructs a single Merkle root from chunks encoding multiple distinct payloads. Note that benefit (3) is contingent on the consensus protocol being revised to vote on the Merkle root commitment rather than the decoded payload; without that change, the equivocation attack surface does not arise in the first place.

## Motivation

MonadBFT uses RaptorCast to disseminate block proposals across the validator set. The current protocol (v0) (see [RaptorCast: Designing a Messaging Layer](https://www.category.xyz/blogs/raptorcast-designing-a-messaging-layer)) places no constraint on which ESI the leader assigns to which position in the Merkle tree, nor on which ESIs are delivered to which validator. This delivery freedom has three consequences that Deterministic RaptorCast addresses.

- **Latency** A natural optimization is to overlap block propagation with consensus voting. Rather than waiting to fully reconstruct a block before casting a vote, a validator that receives a chunk and can verify it against the block's Merkle root could vote immediately—saving one message delay on the consensus critical path. Under v0, however, this is unsafe. Because the leader has freedom over ESI assignment, the same Merkle root can be consistent with multiple distinct payloads; a vote on the root therefore does not unambiguously certify a single block. A canonical (deterministic) encoding removes this ambiguity: since the Merkle root now commits to exactly one possible payload, opening the opportunity for validators to vote on the root as soon as they receive a verified chunk.

- **Attack 1: Asymmetric liveness** Raptor codes decode most efficiently when the decoder receives at least some degree-1 ([singleton](https://www.category.xyz/blogs/raptorcast-designing-a-messaging-layer#2-encoding-system)) ESIs, since these are the entry point for the Belief Propagation peeling decoder. Without any singletons the decoder stalls immediately and must fall back to Gaussian elimination, which is substantially more expensive. A Byzantine leader can exploit v0's delivery freedom to selectively deprive targeted validators of singletons while supplying adversarially chosen high-degree repair chunks that maximize Gaussian elimination cost. The result is that targeted validators reconstruct upto several hundred milliseconds later (depending on the number of source symbols) than the rest of the set which is enough of a delay to starve them of votes in the current view. This gives the leader discretion to force future view failures.

- **Attack 2: Mixed-commitment equivocation** Lowering the latency by voting on the merkle root of encoded chunks involves decode-re-encode consistency check to make sure encoding is valid. Without a fixed ESI-to-position mapping, the decode-re-encode consistency check cannot be correctly defined for rateless codes. A leader can construct a single Merkle root whose leaves are drawn from encodings of multiple distinct payloads. Every chunk passes Merkle verification, but validators collecting different subsets decode to different payloads. If validators vote on the root without decoding, they believe they are certifying the same block while certifying different ones.


## Specification

### Seed Derivation

The canonical seed (also called encoding seed) is computed by the leader at proposal time. It consists of the hash of (round number, leader identity, and proposal time). The chunk header contains all necessary data for validators to deterministically recompute this seed, which they do upon receiving the chunk. Validators also check that the proposal time falls within an acceptable range of their local clock before accepting the seed as valid.

### Encoding

The leader encodes payload `B` as:

```
(c_1, ..., c_n) = RaptorEnc(B, seed)
R               = MerkleRoot(c_1, ..., c_n)
```

In v0, chunks were organized into multiple Merkle trees of `32` chunks each, with each tree independently signed by the leader. v1 replaces this with a 
single global Merkle root `R` computed over all `n` chunks, providing a unified commitment that binds every chunk to a single canonical encoding of 
the proposal. The Merkle tree depth is dynamically calculated based on the  number of chunks, up to a maximum depth of 15. Each Merkle proof is 
`20 × (merkle_tree_depth - 1)` bytes, giving a worst-case proof size of `280` bytes compared to `100` bytes in v0.

Position `i` MUST contain the chunk generated with `ESI = i` under seed. The pair `(R, σ)` where `σ = Sign(round, timestamp, R)` is the ``EncodingCommitment`` for this proposal.

### Chunk Validation

A validator accepts a v1 chunk packet `(round, timestamp, R, σ, i, π_i, c_i)`. A validator accepts the chunk if and only if all of the following holds:

- **Timeliness** The packet's round is within the accepted round window, and the timestamp is within an acceptable range of the validator's local clock.

- **Leader authenticity** `σ` is a valid leader signature over round, timestamp and `R` (`σ = Sign(round, timestamp, R)`).

- **Encoding commitment consistency** `(R, σ)` matches the encoding commitment already recorded for this round. If no commitment is recorded yet, the validator records this one.

- **Chunk integrity** The Merkle proof `π_i` verifies `c_i` at index `i` against `R`.

Chunks failing any check are silently dropped. A conflicting commitment (same round, different `R` or `σ`) is logged as equivocation evidence and the chunk carrying the conflicting commitment is dropped.

### Encoding Verification (Decode-Re-encode Check)

After collecting sufficient chunks and decoding payload B, a validator MUST verify:

```
MerkleRoot(RaptorEnc(B, seed)) == R
```

The seed is deterministically recomputed from the values given in the chunk header. If the above check fails, the payload is rejected. This check is well-defined under v1 because seed fixes the ESI-to-position mapping: re-encoding `B` always produces the same chunk set that can be validated against the recorded ``EncodingCommitment``. Under v0 this check cannot be reliably applied.

## Rationale

Deterministic RaptorCast requires minimal changes to the existing RaptorCast infrastructure. The encoding scheme, Merkle commitments, chunk delivery, and rebroadcast all remain unchanged. The additions are: a canonical seed derived from existing proposal metadata, per-round equivocation detection at each validator. These changes are sufficient to close both attack surfaces and to make voting on the Merkle root commitment safe before decoding, with no changes to the consensus voting protocol, the quorum certificate format, or the execution layer. The resulting protocol satisfies the following properties.

### Properties

Deterministic RaptorCast satisfies the following three properties.

- **Availability** If a Quorum Certificate for a Merkle root `R` exists, every correct validator eventually terminates.

- **Integrity** If the leader is correct, every correct validator that decodes a payload recovers exactly the payload originally dispersed by the leader.

- **Consistency** Any two correct validators that decode a payload from chunks consistent with `R` recover the same payload. If no valid payload is consistent with `R`, every correct validator returns `⊥`.

Consistency is what makes voting on `R` safe prior to decoding. A validator that casts a vote on `R` implicitly vouches for a unique payload: consistency guarantees that every validator that subsequently decodes arrives at the same one. Absent this property, two validators could vote on the same `R` while holding chunks that decode to different payloads, violating consensus safety.

The canonical seed also unlocks a post-consensus validity gate at the execution layer that was not previously applicable. Because the decode-re-encode check produces the same result at every correct validator, it can be applied after consensus has decided a block: any block whose decoded payload fails the check will be independently rejected by every correct validator, with no risk of a split. Under v0 this gate could not be employed without a canonical seed; different validators re-encoding the same payload could produce different roots and reach different conclusions about the same block.

This is enforced by two complementary mechanisms. First, per-round equivocation detection: upon receiving the first valid v1 chunk for a round, each validator records an ``EncodingCommitment`` — the pair (global_merkle_root, signature) — and rejects any subsequent chunk for that round with different fields. Second, the canonical seed fixes the ESI-to-position mapping, making the decode-re-encode check well-defined: re-encoding any decoded payload under the public seed always produces the same chunk set that can be validated against the same ``EncodingCommitment``.

## Security Considerations

The attacks motivating this MIP, asymmetric liveness and mixed-commitment equivocation, are closed by the canonical seed and per-round equivocation detection as described in the Properties section.

- **Seed grinding** The seed construction bounds a Byzantine leader's payload-grinding advantage to negligible within the available window: a leader cannot do better than random chance in selecting a seed that produces a favorable degree distribution within the time bucket.

- **Round window** Chunks outside the accepted round window are silently dropped. This prevents unbounded buffering but means a node that falls significantly behind the current round will not receive chunks for rounds outside its window until it catches up.

## Reference Implementation
The reference implementation can be found at [https://github.com/category-labs/monad-bft/pull/2811](https://github.com/category-labs/monad-bft/pull/2811).
