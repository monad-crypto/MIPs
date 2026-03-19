---
mip: 8
title: Page-ified Storage State
description: Partition EVM storage to align with database pages.
author: Category Labs
discussions-to: https://forum.monad.xyz/t/mip-8-page-ified-storage-state/407
category: Core
created: 2026-03-05
---

## Abstract

Partition EVM storage to align with database pages. Enabling page-level access and warm SLOAD/SSTORE cost for words within a loaded page. 

## Motivation

The EVM abstracts storage as 32-byte `{slot, value}` pairs. This creates a mismatch with modern hardware which operates on 4096-byte pages. Fetching a single 32-byte slot incurs the full I/O cost of a 4KB page. This is roughly an 128× bandwidth underutilization. 

The Merkle Patricia Trie compounds this by hashing keys. This causes logically contiguous slots to be scattered across disjoint pages. Consequently, this related data, is charged for independent disk reads. Some examples include adjacent entries in an order book or a Solidity struct. Hashing of storage keys and the current gas schedule incentives sparse storage layout while providing no benefit for adjacent storage layouts.

To address this we introduce a page abstraction to the EVM storage model.  A page is a fixed-size contiguous group of EVM slots. Pages therefore become the atomic unit for both disk I/O and MPT commitments. Once a page is loaded, subsequent `SLOAD` and `SSTORE` operations on slots within that page are treated as warm. This incentivizes contiguous page-aligned storage layouts. The trie then commits `{page_index, page}` pairs. 

This aligns protocol incentives with hardware reality. Developers are rewarded for contiguous data structures and are not penalized for maintaining current patterns.

## Specification

We introduce the following notation:   

- Storage `slots` are 32 byte values.
- EVM `words` are 32 byte values as defined in the Ethereum Yellow Paper.
- EVM `pages` are 4096 bytes and composed of 128 words. 

For a given slot, we can determine a grouping by modding out the last `n` bits of the key. This naturally stratifies the key space. It allows us to define a page as a contiguous vector of `m` EVM words. In other words, each key maps to `(page_index,offset_within_page)`, and a page stores `m` consecutive EVM words. The mapping functions from `slot` to `page` information is defined as follows:

- `page_index(slot) = slot >> 7`
- `offset(slot) = slot & 0x7F`

### Page Commitment Function

BLAKE3 internally constructs a Merkle tree over 1024-byte chunks. As such the native BLAKE3 tree supports inclusion proofs at the 1024-byte leaf granularity. Efficient single-word inclusion proofs are not directly supported. To recover this property, we define a commitment function using BLAKE3’s compression function. 

Intuitively, this commitment function is a 32-byte merkle root over a 4096-byte page using a fixed binary tree built from the BLAKE3 compression function.

Let `P` be a 4096-byte page. Then note the following:

1. The BLAKE3 compression function operates on 64-byte blocks.
2. The page is partitioned into 64 pair-leaves where each leaf consists of two consecutive 32-byte words.
3. Internal nodes form a fixed binary merkle tree. 

Each internal node is computed by hashing the concatenation of its two 32-byte child hashes using the BLAKE3 compression function. The resulting root is the page commitment. 

**Reference implementation**

A full reference is linked at the end of the file. This includes optimizing for simd. Below is a minimal reference implementation of the commitment function:

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

### Leaves of Merkle-Patricia Trie

The Merkle Patricia Trie commits to `{page_index_i: page_commit(page_i)}` pairs where `page_commit(page_i)` is a 32-byte commitment to the contents of a page.  

This trie has the following modifications:

1. **Hash Function**: Blake3
2. **Leaf values**: For each `page_index`, define the corresponding leaf value as page commitment of the index i page.
3. **Leaf placement**: Each `page_index` uniquely determines a path from the MPT root to its leaf. This path is computed exactly as in a standard MPT using the `page_index` as the key.
4. **Trie structure**: The MPT structure is unchanged otherwise: branch, extension, and leaf nodes follow the standard MPT rules.
5.  **On-demand computation**: The value of each storage leaf is exactly 32 bytes, so the `page_commit(page)` can be recomputed from the page contents whenever needed. No additional storage layout changes are required.
6. **Merkle Proofs**: Merkle proofs for page commitments are unchanged from a standard MPT. However, this proof only proves that a certain page has been committed. 

### Word Inclusion Proofs

The page commit can be thought of as a fixed size merkle tree stored inside the MPT leaf. Given a merkle proof for a page commitment, we can prove the inclusion of any specific word within that page. To construct an inclusion proof for a particular word, we need the following:

| Field            | Size     | Description                                                                                     |
| ---------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `word_idx`       | usize    | Position of the word within the page (0–127). Caller-provided, not part of cryptographic proof. |
| `word`           | 32 B     | Value of the target word.                                                                       |
| `sibling_word`   | 32 B     | Companion word in the same pair-leaf.                                                           |
| `parent_sibling` | 6 × 32 B | Sibling hashes at each parent level (pair-leaf → parent).                                       |


As a result, the inclusion proof for any individual word consists of two components: The inclusion proof of the word within its page commitment; The inclusion proof of the page commitment within the MPT.  The total proof size is the sum of these components in the worse case.

## Gas Cost

We assume the following: 

1. Let `read_accessed_pages` be the set of read pages accessed during the current transaction;
2. Let `write_accessed_pages` be the set of write pages accessed during the current transaction;
3. and let `p = page_index(s).`

### SLOAD Gas Schedule

We define the `SLOAD` cost in terms of pages as the following: 

- If `p` is in `read_accessed_pages` then charge BASE_SLOAD_COST gas;
- Otherwise charge COLD_SLOAD_COST gas and add `p` to `read_accessed_pages`.

### SSTORE Gas Schedule

We define the `SSTORE` cost in terms of pages and state transitions. 

Let `P0` be the initial value of the page `p` for a given `SSTORE` and let `P1`  be the terminal value of page `p` immediately after the `SSTORE`.  The following is the I/O cost for the writing the page to the hardware.



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

Besides the I/O cost component for a page write, the remainder of the SSTORE cost is computed based on the net state growth of the page. The main difference from the current evm cost is that the state growth cost are only deducted if the transaction is increasing the net state of the page. If a slot is created to replace a previously cleared slot in the same page then the growth fee is bypassed. This is defined so that gas remaining is monotonically decreasing to align with current gas model. This is defined as the following: 

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

Contracts that allocate storage in contiguous chunks aligned to page boundaries are economically optimal. They benefit from lower gas costs and more efficient inclusion proofs. 

If a page contains only a single populated element then the remaining positions are zero. The page commitment can therefore be reconstructed without additional hashes. So single-slot proofs incur no overhead from page commitment hashes. Therefore proof size remains stable for current mapping-based state. Since two random keys collide in the same page with probability  1 in 2²⁴⁹.  

More generally, if a page contains only a contiguous set of words then the page commitment can therefore be reconstructed without additional hashes. The effect is that proof size also remains stable for contiguous storage allocations. Therefore contiguous multi-word inclusion proofs are strictly more efficient.

In the case where a page is sparsely populated at random, single-word inclusion proofs incur a small fixed overhead. However, inclusion proofs of either single words or contiguous multi-word  in the same page are amortizated since they share the main merkle proof component.

## **Backwards Compatibility**

The EVM semantics remain unchanged under this update. The only modification is paging effect to the gas schedule. 

Existing contracts that access consecutive storage slots will observe reduced execution costs with high probability. Notably this is in effect for contracts that utilized solidity `structs`, state variable layout, or arrays.

The only class of contracts that are negatively impacted are those that explicitly rely on hardcoded opcode gas costs associated with consecutive storage accesses; all other contracts remain functionally unchanged.

## **Security Considerations**

## Page Index Space Size

The current Merkle Patricia Trie uses a 2²⁵⁶ key space. Keys are hashed to determine leaf placement. This ensures that the tree remains balanced. The effective key space is reduced to 2²⁴⁹ in the paged state scheme. This reduction does not affect the tree structure. The hash still forces a uniform distribution. The MPT topology and security properties are therefore preserved.

## Page Size

Each leaf of the current Merkle Patricia Trie corresponds to a single EVM storage slot currently. We considered 2, 4, 8, 16, 32, 64, and 128 words per page. Each of these page sizes is at most 4096 bytes of raw slot data. So they fit within a I/O page. (This ignores any node metadata overhead.)

A consideration is that storage page may span multiple I/O pages. We can estimate the probability that a storage page crosses a I/O page boundary using uniform random offsets (assuming storage page is completely full):

| Page Size | Probability of crossing I/O page | Worse Case Block Slowdown |
| --------- | -------------------------------- | ------------------------- |
| 1 words   | ~1%                              | 1.01x                     |
| 2 words   | ~1%                              | 1.01x                     |
| 4 words   | ~3%                              | 1.03x                     |
| 8 words   | ~6%                              | 1.06x                     |
| 16 words  | ~12%                             | 1.12x                     |
| 32 words  | ~25%                             | 1.25x                     |
| 64 words  | ~50%                             | 1.5x                      |
| 128 words | ~100%                            | 2.00x                     |

If a storage page straddles multiple I/O pages then a single EVM `SSTORE/SLOAD` can underprice storage operations due to read amplification. In practice recent storage is cached. So these effects are usually mitigated.

To reason about the worst case, consider a single block of EVM execution where an attacker controls all storage writes. If storage pages cross I/O boundaries, `SLOAD` operations for misaligned portions could be effectively 2× slower. To achieve this, an attacker would need to allocate an entire page and then wait until the relevant pages are no longer cached. 


## Future Directions

BLAKE3 provides a flexible framework for defining fixed-size Merkle trees over “black-box” hash functions. This flexibility enables a correspondence between trees of different fanouts. In the MIP-9, we explore this correspondence to reduce inclusion proof size, minimize Merklization overhead, and optimize storage writes. 

## **Copyright**

Copyright and related rights waived via [CC0](https://github.com/monad-crypto/MIPs/blob/main/LICENSE.md).