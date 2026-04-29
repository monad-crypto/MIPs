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

We introduce key locality to the Merkle Patricia Trie by adding a page abstraction to the state model, enabling page-level access and warm `SLOAD`/`SSTORE` cost for any slot within a loaded page.

## Motivation

The EVM abstracts storage as 32-byte `{slot, value}` pairs. The gas schedule of this model is tied to the commitment scheme of the Merkle Patricia Trie, since the trie acts on these pairs. This creates a dilemma: mapping the MPT to disk causes access to a 32-byte slot to require loading an entire 4KB page, while optimizing the physical disk layout independently leaves the commitment layer bound to the original slot-based pricing model. 

In either case, the inefficiency is propagated by the application layer and the state layer. At the application layer, high-level languages such as Solidity rely heavily on `keccak256` hashing for mapping layouts. This causes related data to be assigned to pseudorandom storage locations. At the state layer, the MPT hashes keys before commitment, so sequential slot updates modify disjoint regions of the trie. These factors cause logically contiguous slots to be scattered across disjoint pages, resulting in related data being charged as independent disk reads. 

To address this, we introduce a page abstraction to the state model.  A page is a fixed-size contiguous group of EVM slots. Pages become the atomic unit for both disk I/O and MPT commitments. Once a page is loaded, subsequent `SLOAD` and `SSTORE` operations on slots within that page are treated as warm. The trie then commits `{page_index, page}` pairs. 

Standard EVM execution semantics and backward compatibility with existing gas pricing are preserved. Common storage patterns in Solidity naturally benefit from page warming. For example, mappings to structs benefit because a struct’s internal fields occupy contiguous storage slots once the mapping entry is resolved. This preserves existing smart contract development best practices while incentivizing contiguous storage grouping.

## Specification

We introduce the following notation:   

- Storage `slots` are 32 byte values.
- EVM `words` are 32 byte values as defined in the Ethereum Yellow Paper.
- EVM `pages` are 4096 bytes and composed of 128 words. 

For a given slot, we determine its grouping by stripping the lower 7 bits of the key. This stratifies the key space and lets us define a page as a contiguous vector of 128 EVM words. Each key maps to `(page_index, offset_within_page)`, where a page stores 128 consecutive EVM words. The mapping functions from `slot` to `page` information are defined as follows:

- `page_index(slot) = slot >> 7`
- `offset(slot) = slot & 0x7F`

### Page Commitment Function

BLAKE3 supports inclusion proofs at the 1024-byte leaf granularity since internally it constructs a Merkle Tree over 1024-byte chunks. However, efficient single-word inclusion proofs are not natively supported. 

To recover this property, we define a commitment function that computes a 32-byte Merkle root over a 4096-byte page by constructing an induced subtree using BLAKE3. This commitment function, referred to as the Induced Subtree Merkle Commit (ISMC), commits only to the occupied state.

Let `P` be a 4096-byte page. Then note the following:

1. The BLAKE3 compression function operates on 64-byte blocks.
2. The page is partitioned into 64 pair-leaves where each leaf consists of two 32-byte words. Pair-leaf occupancy is tracked via a 64-bit bitmap, while a 128-bit slot bitmap is used for the commitment.
3. Internal nodes form an induced subtree determined by occupancy of pair-leaves, topologically bypassing empty branches entirely. Singletons are carried up the tree without requiring empty hash operations.
4. The commit is done in two phases:
    1. **Merge Phase**: A bottom-up reduction of the occupied pair-leaves. This captures the payload of all active data in the page.
    2. **Seal Phase**: The resulting subtree root is hashed alongside the 128-bit slot bitmap. This uniquely binds the data to the exact geometric positions and prevents spatial collisions.
5. Execution and proof size scale with occupancy. The **merge phase** costs exactly `k - 1` compressions, where `k` is the number of active pairs.

The resulting root is the **page commitment**. A Python pseudocode implementation of this commitment is shown below. A full breakdown of this commitment function can be found in the paper titled Merkle Commitments via Induced Subtrees.

**Reference implementation**

```python
Function ISMC_Commit(page, slot_bitmap):
    // Inputs:
    // page: 4096-byte array (64 pairs of 64 bytes)
    // slot_bitmap: 128-bit integer representing exact 32-byte word occupancy
    
    // Convert 128-bit slot bitmap to 64-bit pair bitmap (1 if either word in pair is active)
    pair_bitmap = reduce_to_pair_bitmap(slot_bitmap)
    
    // --- Phase 1: Data Merge Phase ---
    active_nodes = []
    
    // Extract only occupied pair-leaves (Bypassing empty branches)
    For i from 0 to 63:
        If bit i is set in pair_bitmap:
            pair_data = page[i * 64 : (i + 1) * 64]
            active_nodes.append({ index: i, value: pair_data })
            
    // Bottom-up reduction 
    For level from 0 to 5:
        next_level_nodes = []
        i = 0
        
        While i < length(active_nodes):
            current_node = active_nodes[i]
            
            // Check if a right sibling exists in the active nodes
            If i + 1 < length(active_nodes):
                next_node = active_nodes[i + 1]
                
                // Nodes are siblings if they share the same parent at the next level
                If (current_node.index >> (level + 1)) == (next_node.index >> (level + 1)):
                    // Hash the two 32-byte children into a new 32-byte parent
                    parent_value = BLAKE3_Hash(current_node.value || next_node.value)
                    next_level_nodes.append({ index: current_node.index, value: parent_value })
                    i += 2
                    continue
            
            // Singleton Case: Carry up without hashing
            next_level_nodes.append(current_node)
            i += 1
            
        active_nodes = next_level_nodes
        
        // Early exit: The tree is fully reduced to a single root
        If length(active_nodes) == 1:
            break
            
    subtree_root = active_nodes[0].value
    
    // --- Phase 2: Structural Seal Phase ---
    // Uniquely bind the subtree root to the exact geometric layout
    seal_payload = concatenate(slot_bitmap, subtree_root)   // 16 bytes + 32 bytes
    page_commitment = BLAKE3_Hash(seal_payload)
    
    Return page_commitment
```
### Inclusion Proofs

Intuitively, the ISMC can be viewed as an embedded Merkle tree that proves the exact state of a 4096-byte page. Given a page commitment, we can efficiently prove the inclusion of any specific 32-byte word within that page.

To construct an inclusion proof for a particular word, the verifier must be able to recompute the page commitment using the merge schedule. Therefore, an ISMC inclusion proof consists of exactly two components:

1. The 128-bit slot bitmap: Required to deterministically reconstruct the tree's geometry and prove the exact spatial index of the word.
2. The sibling hashes: The minimal set of sibling hashes required to route from the target word to the subtree root under the induced merge schedule.

The inclusion proof size scales strictly with the occupancy of the page rather than its physical size. Let `k` be the number of active leaves; the maximum tree depth is 6. The number of sibling hashes along a leaf's path is at most `min(k - 1, 6)`. Therefore, the worst-case inclusion proof size for a word is strictly bounded by `min(k - 1, 6) * 32 bytes + 16 bytes`.

### Leaves of Merkle-Patricia Trie

The Merkle Patricia Trie commits to `{page_index_i: page_commit(page_i)}` pairs where `page_commit(page_i)` is a 32-byte commitment to the contents of a page.  

This trie has the following modifications:

1. **Hash Function**: Keccak.
2. **Leaf values**: For each `page_index`, the corresponding leaf value is the page commitment of the page at that index.
3. **Leaf placement**: Each `page_index` uniquely determines a path from the MPT root to its leaf. This path is computed exactly as in a standard MPT, using the `page_index` as the key.
4. **Trie structure**: The MPT structure is otherwise unchanged: branch, extension, and leaf nodes follow the standard MPT rules.
5. **On-demand computation**: The value of each storage leaf is exactly 32 bytes, so `page_commit(page)` can be recomputed from the page contents whenever needed. No additional storage layout changes are required.
6. **Merkle Proofs**: Merkle proofs for page commitments are unchanged from a standard MPT. Such a proof only proves that a particular page has been committed.

As a result, the inclusion proof for any individual word consists of two components: the inclusion proof of the word within its page commitment, and the inclusion proof of the page commitment within the MPT. The total proof size is the sum of these components.


## Gas Cost

We assume the following: 

1. Let `read_accessed_pages` be the set of read pages accessed during the current transaction;
2. Let `write_accessed_pages` be the set of write pages accessed during the current transaction;
3. and let `p = page_index(s).`
4. `BASE_COST` is 100 gas;
5. `LOAD_COST` is 8000 gas;
6. `WRITE_COST` is 2800 gas;
7. `STATE_GROWTH_COST` is 17000 gas.


### SLOAD Gas Schedule

We define the `SLOAD` cost in terms of pages as the following: 

```python
# Page is cached then charge base cost. 
if p in read_accessed_pages: 
    gas_deducted += BASE_COST
# Page is not cached charge load cost.
else: 
    gas_deducted += LOAD_COST + BASE_COST
    read_accessed_pages.append(p)
```

### SSTORE Gas Schedule

We define the `SSTORE` cost as the sum of an I/O write cost and a state transition cost, both computed per `SSTORE`. As in legacy `SSTORE`, we apply the `LOAD_COST` if the page is cold.

### Write Cost

Let `P0` be the initial value of page `p` for a given `SSTORE`, and let `P1` be the terminal value of page `p` immediately after the `SSTORE`.

The following is the I/O cost for writing the page to the hardware.


```python
# PAGE I/O Cost

# `BASE_COST` is deducted in all cases.
gas_deducted += BASE_COST

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
        gas_deducted += WRITE_COST

        # Page has been charged write cost
        write_accessed_pages.append(p)

        # Page has not been loaded to cache
        if p not in read_accessed_pages:
            gas_deducted += LOAD_COST
            read_accessed_pages.append(p)

        # instantiate state growth counters
        current_state_growth[p] = 0
        net_state_growth[p] = 0  
        
    
```
### State Transition Cost

The remainder of the `SSTORE` cost is computed based on the net effect of state growth. The state growth cost is only deducted if the transaction increases the net state of the page. If a slot is created to replace a previously cleared slot in the same page, the growth fee is bypassed. This is defined so that gas remaining is monotonically decreasing, aligning with the current gas model's assumptions. These costs are defined per page; there is no cross-page subsidization.
```python
# State Transition Cost

# add to current state counter growth if page state increases
if v_current == 0 and v_new != 0:
	current_state_growth[p] += 1
	
# subtract state growth counter if page state decreases
elif v_current != 0 and v_new == 0:
    current_state_growth[p] -= 1
    
# if net state growth has increased then charge for state growth
if current_state_growth[p] > net_state_growth[p] :
	  gas_deducted += STATE_GROWTH_COST
	  net_state_growth[p]  = current_state_growth[p]
```

During execution, if a call reverts, the counters `current_state_growth` and `net_state_growth` must revert to their values from before that call to maintain price consistency.

## Rationale

Contracts that allocate storage in contiguous chunks aligned to page boundaries are economically optimal, benefiting from lower gas costs and highly efficient inclusion proofs. Because the page commitment execution and proof size scale with the number of active pairs, the architecture natively aligns with the EVM’s storage patterns:

1. **Random Sparse State**: The probability of two randomly hashed keys colliding within the same page is approximately 1 in 2**249. A standard mapping slot is therefore likely to be the only populated element in its page, and its page commitment can be reconstructed with zero sibling hashes. Proof sizes for current mapping-based states remain stable outside of the bitmap overhead.
2. **Contiguous State**: When a page contains a densely packed, contiguous set of words, a multi-word inclusion requires only the sibling hashes along the outer boundary of the data block. This amortizes the proof size per word, making contiguous multi-word inclusion proofs strictly more efficient, again outside of the bitmap overhead.
3. **Amortized Sparse Reads**: When a page is sparsely populated at random, single-word inclusion proofs incur a small, bounded overhead within the page. Under a uniform distribution, the expected proof size grows logarithmically as `O(log k)`.

BLAKE3 was chosen for its hashing speed, amenability to zk proof generation, and the BAO construction. This allows for faster merklization in both the standard case and proof generation. Applying BLAKE3 to the entire Merkle tree also enables bytecode inclusion proofs via the BAO construction.

## Backwards Compatibility

The EVM semantics remain unchanged under this update. The only modification is the introduction of page-level access warming to the gas schedule.

Existing contracts that access consecutive storage slots will automatically observe reduced gas costs. This update does not require developers to adopt bespoke storage architectures or non-standard upgrade patterns to realize benefits:

- **No Penalty for Dispersed State:** Existing hashed patterns and dispersed state layouts are not penalized; they simply maintain their historical baseline cost. For example, reading a standard `mapping(address => Struct)` will execute the initial mapping lookup at the baseline gas cost. However, all subsequent reads to that specific user's struct fields will benefit from the new warm-page gas discounts.
- **Solidity:** Standard Solidity features natively allocate data in consecutive slots. Common primitives such as structs, densely packed state variables, and arrays will seamlessly inherit these gas optimizations without developer intervention.
- **Unaligned Legacy Layouts:** Conventional upgradeable contract patterns may not perfectly align with 128-word page boundaries. While developers of future contracts may choose to hyper-optimize layouts to capture maximal page-warming discounts, failing to do so incurs no penalty. Misaligned or "cold" reads across page boundaries simply execute at the standard baseline cost.

The only class of contracts impacted by this update are those that explicitly rely on hardcoded opcode gas costs associated with storage accesses. All other contracts remain functionally unchanged.

**EIP-2930 Access Lists**

The transaction payload format for [EIP-2930](https://eips.ethereum.org/EIPS/eip-2930) access lists is backwards compatible.  If an access list contains multiple keys that map to the same 128-word page then the cold-access cost is charged only once and applies the warm-access cost to all subsequent keys within that boundary.

**RPC Modifications**

1. The RPC method `eth_getProof` must be updated to return the modified proof structure.
2. The RPC method `eth_createAccessList` must be updated as above to return an updated `gasUsed` estimate.
3. `eth_estimateGas`, `eth_call`, and `trace_call` should reflect the updated gas schedule.


## Security Considerations

### Page Index Space Size

The current Merkle Patricia Trie uses a 2**256 key space, with keys hashed to determine leaf placement so that the tree remains balanced. Under the paged state scheme, the effective key space is reduced to 2**249. This reduction does not affect the tree structure: the hash still forces a uniform distribution, so the MPT topology and security properties are preserved.

### Page Size

Each leaf of the current Merkle Patricia Trie corresponds to a single EVM storage slot. We considered 2, 4, 8, 16, 32, 64, and 128 words per page. Each of these page sizes is at most 4096 bytes of raw slot data, so they fit within an I/O page (ignoring any node metadata overhead).

A storage page may span multiple I/O pages. We can estimate the probability that a storage page crosses an I/O page boundary using uniform random offsets (assuming the storage page is completely full):

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

When a storage page straddles multiple I/O pages, a single EVM `SSTORE`/`SLOAD` can underprice storage operations due to read amplification. In practice, recent storage is cached, so these effects are usually mitigated.

To reason about the worst case, consider a single block of EVM execution in which an attacker controls all storage writes. If storage pages cross I/O boundaries, `SLOAD` operations for misaligned portions could be effectively 2× slower. To achieve this, an attacker would need to allocate an entire page and then wait until the relevant pages are no longer cached.

## Related Prior Art

It should be noted that [EIP-7864](https://eips.ethereum.org/EIPS/eip-7864) introduces a similar page-structure property by grouping 256 slots into structured subtrees. However, this localization is achieved as a secondary side effect of fundamentally restructuring the entire state commitment tree with its costs defined by the [EIP-4762](https://eips.ethereum.org/EIPS/eip-4762) gas schedule.

## Future Directions

In a future MIP, we explore the correspondence between binary commitments and high-fanout trees to further reduce expected proof size and minimize merklization complexity.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
