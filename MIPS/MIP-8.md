---
mip: 8
title: Page-ified Storage State
description: Partition EVM storage to align with database pages
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-8-page-ified-storage-state/407
status: Draft
type: Standards Track
category: Core
created: 2026-03-05
---

## Abstract

This MIP partitions EVM storage to align with database pages, enabling page-level access and warm `SLOAD`/`SSTORE` pricing for any word within a loaded page.

## Motivation

The EVM abstracts storage as 32-byte `{slot, value}` pairs. This creates a mismatch with modern hardware, which operates on 4096-byte pages: fetching a single 32-byte slot incurs the full I/O cost of a 4KB page, an approximately 128× bandwidth underutilization.

The Merkle Patricia Trie compounds this problem by hashing keys, which scatters logically contiguous slots across disjoint pages. As a result, related data such as adjacent entries in an order book or fields of a Solidity struct are charged for independent disk reads. Together, key hashing and the current gas schedule incentivize sparse storage layouts while providing no benefit for adjacent ones.

To address this, we introduce a page abstraction to the EVM storage model. A page is a fixed-size contiguous group of EVM slots, and pages become the atomic unit for both disk I/O and MPT commitments. Once a page is loaded, subsequent `SLOAD` and `SSTORE` operations on slots within that page are treated as warm, which incentivizes contiguous, page-aligned storage layouts. The trie then commits `{page_index, page}` pairs.

This aligns protocol incentives with hardware reality: developers are rewarded for using contiguous data structures and are not penalized for retaining current patterns.

## Specification

We introduce the following notation:

- Storage `slots` are 32-byte values.
- EVM `words` are 32-byte values, as defined in the Ethereum Yellow Paper.
- EVM `pages` are 4096 bytes, composed of 128 words.

For a given slot, we determine its grouping by masking the low `n` bits of the key. This stratifies the key space and lets us define a page as a contiguous vector of `m` EVM words. Equivalently, each key maps to `(page_index, offset_within_page)`, and a page stores `m` consecutive EVM words. The mapping from a `slot` to its `page` information is defined as follows:

- `page_index(slot) = slot >> 7`
- `offset(slot) = slot & 0x7F`

### Page Commitment Function

BLAKE3 internally constructs a Merkle tree over 1024-byte chunks, so the native BLAKE3 tree supports inclusion proofs only at the 1024-byte leaf granularity; efficient single-word inclusion proofs are not directly supported. To recover this property, we define a commitment function built on BLAKE3's compression function.

Intuitively, this commitment function is a 32-byte Merkle root over a 4096-byte page, computed as a fixed binary tree of BLAKE3 compressions.

Let `P` be a 4096-byte page. The construction is as follows:

1. The BLAKE3 compression function operates on 64-byte blocks.
2. The page is partitioned into 64 pair-leaves, where each leaf consists of two consecutive 32-byte words.
3. Internal nodes form a fixed binary Merkle tree.

Each internal node is computed by hashing the concatenation of its two 32-byte child hashes with the BLAKE3 compression function. The resulting root is the page commitment.

**Reference implementation**

A full reference, including SIMD optimizations, is linked at the end of this document. A minimal reference implementation of the commitment function is shown below:

```python
from blake3_compress import compress, words_to_bytes, bytes_to_words, IV

CHUNK_START         = 1
CHUNK_END           = 2
DERIVE_KEY_MATERIAL = 64

_PAIR_LEAF_KEY = b"ultra_merkle_pair_leaf_domain___"
assert len(_PAIR_LEAF_KEY) == 32

def _derive_leaf_iv():
    key_block = _PAIR_LEAF_KEY + bytes(32) 
    return compress(IV, key_block, 64, 0, DERIVE_KEY_MATERIAL)  
    
LEAF_IV = _derive_leaf_iv()

def hash_leaf(block_64):
    assert len(block_64) == 64
    return words_to_bytes(compress(LEAF_IV, block_64, 64, 0, DERIVE_KEY_MATERIAL))

def hash_parent(children):
    assert len(children) == 2
    block = b"".join(children)
    assert len(block) == 64

    return words_to_bytes(
        compress(IV, block, 64, 0, CHUNK_START | CHUNK_END)
    )

def page_commit(data):
    """
    Fully unrolled binary Merkle root of a 4096-byte page.
    Returns 32 bytes.
    """
    assert len(data) == 4096

    l0 = [hash_leaf(data[i*64:(i+1)*64]) for i in range(64)]

    l1 = [hash_parent([l0[i], l0[i+1]]) for i in range(0, 64, 2)]

    l2 = [hash_parent([l1[i], l1[i+1]]) for i in range(0, 32, 2)]

    l3 = [hash_parent([l2[i], l2[i+1]]) for i in range(0, 16, 2)]

    l4 = [hash_parent([l3[i], l3[i+1]]) for i in range(0, 8, 2)]

    l5 = [hash_parent([l4[i], l4[i+1]]) for i in range(0, 4, 2)]

    root = hash_parent([l5[0], l5[1]])

    return root
```

### Leaves of the Merkle Patricia Trie

The Merkle Patricia Trie commits to `{page_index_i: page_commit(page_i)}` pairs, where `page_commit(page_i)` is a 32-byte commitment to the contents of page `i`.

This trie incorporates the following modifications:

1. **Hash function**: BLAKE3.
2. **Leaf values**: for each `page_index`, the corresponding leaf value is the page commitment of the page at that index.
3. **Leaf placement**: each `page_index` uniquely determines a path from the MPT root to its leaf. This path is computed exactly as in a standard MPT, using the `page_index` as the key.
4. **Trie structure**: the MPT structure is otherwise unchanged; branch, extension, and leaf nodes follow the standard MPT rules.
5. **On-demand computation**: the value of each storage leaf is exactly 32 bytes, so `page_commit(page)` can be recomputed from the page contents whenever needed. No additional storage layout changes are required.
6. **Merkle proofs**: Merkle proofs for page commitments are unchanged from a standard MPT. However, such a proof only establishes that a particular page has been committed.

### Word Inclusion Proofs

The page commitment can be thought of as a fixed-size Merkle tree stored inside the MPT leaf. Given a Merkle proof for a page commitment, we can prove the inclusion of any specific word within that page. To construct an inclusion proof for a particular word, we need the following:

| Field            | Size     | Description                                                                                         |
| ---------------- | -------- | --------------------------------------------------------------------------------------------------- |
| `word_idx`       | usize    | Position of the word within the page (0–127). Caller-provided, not part of the cryptographic proof. |
| `word`           | 32 B     | Value of the target word.                                                                           |
| `sibling_word`   | 32 B     | Companion word in the same pair-leaf.                                                               |
| `parent_sibling` | 6 × 32 B | Sibling hashes at each parent level (pair-leaf → root).                                             |


An inclusion proof for any individual word therefore consists of two components: the inclusion proof of the word within its page commitment, and the inclusion proof of the page commitment within the MPT. The total proof size is the sum of these components in the worst case.

## Gas Cost

We adopt the following definitions:

1. Let `read_accessed_pages` be the set of pages read during the current transaction.
2. Let `write_accessed_pages` be the set of pages written during the current transaction.
3. Let `p = page_index(s)` for the slot `s` being accessed.

### SLOAD Gas Schedule

We define the `SLOAD` cost in terms of pages as follows:

- If `p` is in `read_accessed_pages`, charge `BASE_SLOAD_COST` gas.
- Otherwise, charge `COLD_SLOAD_COST` gas and add `p` to `read_accessed_pages`.

### SSTORE Gas Schedule

We define the `SSTORE` cost in terms of pages and state transitions.

Let `P0` be the initial value of page `p` for a given `SSTORE`, and let `P1` be its value immediately after the `SSTORE`. The following is the I/O cost of writing the page to disk.



```python
# PAGE I/O Cost

# Page did not change for this SSTORE
if P0 == P1:
    gas_deducted += 0

# Page did change for this SSTORE
else:
	# Page already charged write
	if p in write_accessed_pages:
    gas_deducted += 0

	# Page charged first write only
	else:
    write_accessed_pages.add(p)
    gas_deducted += PAGE_WRITE_COST
```

Beyond the I/O component of a page write, the remainder of the `SSTORE` cost is computed from the net state growth of the page. The key difference from the current EVM cost model is that state-growth cost is only charged when the transaction increases the net populated state of the page. If a new slot is created to replace a previously cleared slot in the same page, the growth fee is bypassed. This rule is defined so that gas remaining is monotonically decreasing, consistent with the current gas model. The schedule is as follows:

```python

# initial value at start of transaction
slot_delta_counter[P] = 0
max_nonzero_slots[P] = 0  

# Creating a new slot | 0 -> 0 -> Z |
if v_original == 0 and v_current == 0 and v_new != 0:
    gas_deducted += BASE_SSTORE_COST
    slot_delta_counter[P] += 1

	# If the current growth exceeds the previous peak then charge state growth
    if slot_delta_counter[P] > max_nonzero_slots:
	    gas_deducted += NEW_SLOT_COST
	    max_nonzero_slots = slot_delta_counter[P]
    
# Clear an existing slot | X -> Y -> 0 | X -> X -> 0 |
elif v_original != 0 and v_current != 0 and v_new == 0:
    gas_deducted += BASE_SSTORE_COST
    slot_delta_counter[P] -= 1

# Writing zero to zero | 0 -> Y -> 0 |
elif v_original == 0 and v_current != 0 and v_new == 0:
		gas_deducted += 0
		slot_delta_counter[P] -= 1

# Restoring a cleared slot | X -> 0 -> Z | X -> 0 -> X |
elif v_original != 0 and v_current == 0 and v_new != 0:
    gas_deducted += BASE_SSTORE_COST
    slot_delta_counter[P] += 1

# Write Nonzero to Nonzero and remaining cases | X -> Y -> X | X -> X -> Z |
else: 
    gas_deducted += BASE_SSTORE_COST

```

## Rationale

Contracts that allocate storage in contiguous, page-aligned chunks are economically optimal: they benefit from both lower gas costs and more efficient inclusion proofs.

When a page contains only a single populated element, all other positions are zero, so the page commitment can be reconstructed without additional hashes. Single-slot proofs therefore incur no overhead from page-commitment hashing, and proof size remains stable for current mapping-based state, since two random keys collide in the same page with probability 1 in 2²⁴⁹.

More generally, if a page contains only a contiguous set of populated words, the page commitment can again be reconstructed without additional hashes. As a result, proof size remains stable for contiguous storage allocations, and contiguous multi-word inclusion proofs are strictly more efficient.

When a page is sparsely populated at random, single-word inclusion proofs incur a small fixed overhead. However, inclusion proofs for either single words or contiguous word ranges within the same page are amortized, since they share the main Merkle proof component.

## Backwards Compatibility

EVM semantics are unchanged by this update; the only modification is the paging behavior of the gas schedule.

Existing contracts that access consecutive storage slots will, with high probability, observe reduced execution costs. This applies in particular to contracts that use Solidity `structs`, packed state-variable layouts, or arrays.

The only contracts negatively impacted are those that explicitly rely on hardcoded opcode gas costs for consecutive storage accesses; all other contracts remain functionally unchanged.

## Security Considerations

### Page Index Space Size

The current Merkle Patricia Trie uses a 2²⁵⁶ key space, and keys are hashed before leaf placement to keep the tree balanced. Under the paged scheme, the effective key space is reduced to 2²⁴⁹. This reduction does not affect the tree structure: the hash still induces a uniform distribution, so the MPT's topology and security properties are preserved.

### Page Size

Each leaf of the current Merkle Patricia Trie corresponds to a single EVM storage slot. We considered page sizes of 2, 4, 8, 16, 32, 64, and 128 words. Each of these holds at most 4096 bytes of raw slot data and therefore fits within a single I/O page (ignoring node metadata overhead).

One consideration is that a storage page may span multiple I/O pages. Assuming uniform random offsets and a fully populated storage page, we can estimate the probability that a storage page crosses an I/O page boundary:

| Page Size | Probability of crossing I/O page | Worst Case Block Slowdown |
| --------- | -------------------------------- | ------------------------- |
| 1 word    | ~1%                              | 1.01x                     |
| 2 words   | ~1%                              | 1.01x                     |
| 4 words   | ~3%                              | 1.03x                     |
| 8 words   | ~6%                              | 1.06x                     |
| 16 words  | ~12%                             | 1.12x                     |
| 32 words  | ~25%                             | 1.25x                     |
| 64 words  | ~50%                             | 1.5x                      |
| 128 words | ~100%                            | 2.00x                     |

When a storage page straddles multiple I/O pages, a single `SSTORE` or `SLOAD` can underprice the operation due to read amplification. In practice, recent storage is cached, which usually mitigates this effect.

To reason about the worst case, consider a block of EVM execution in which an attacker controls all storage writes. If storage pages cross I/O boundaries, `SLOAD` operations for misaligned portions could be effectively 2× slower. To exploit this, an attacker would have to allocate an entire page and wait until the relevant pages were evicted from cache.


## Future Directions

BLAKE3 provides a flexible framework for defining fixed-size Merkle trees over "black-box" hash functions, which enables a correspondence between trees of different fanouts. MIP-9 explores this correspondence to reduce inclusion proof size, minimize Merklization overhead, and optimize storage writes.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
