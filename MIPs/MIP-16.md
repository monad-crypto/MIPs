---
mip: 16
title: JSON-RPC Query Methods
description: JSON-RPC methods that enable efficient queries for raw chain history data
author: Kevin Koste (@typedarray), Kyle Scott (@kyscott18), Jay Miller, Andre Benedito
discussions-to: https://forum.monad.xyz/t/draft-mip-json-rpc-query-methods/546
status: Review
type: Standards Track
category: Interface
created: 2026-09-21
---

## Abstract

This MIP introduces five new JSON-RPC methods that enable efficient queries for raw chain history data:

- `eth_queryBlocks`
- `eth_queryTransactions`
- `eth_queryLogs`
- `eth_queryTraces`
- `eth_queryTransfers`

Each method scans a contiguous block range, oldest-first or newest-first, and returns the objects that match a server-side filter, such as sender, recipient, function selector, or event topic. A request can select exactly which fields to return, and can join each result's block and transaction into the same response. Results are paginated by block: a page never splits a block, and each response reports the last block it covers as `cursorBlock`, so clients resume from the next block without repeating or skipping results. Every response also includes the hash and parent hash of its boundary blocks, which lets clients detect reorgs without extra requests.

## Motivation

The standard Ethereum JSON-RPC interface provides inadequate primitives for querying chain history. Many useful queries are not possible, and the queries that are supported suffer from overfetching and inefficient pagination.

This proposal aims to address four specific shortcomings.

- **Filtering.** The `eth_getLogs` method supports log filtering, but there is no efficient way to filter transactions or traces. To query all transactions sent to a specific address, the user must fetch entire blocks and filter client-side.
- **Relations.** There is no way to join related objects in a single request. To fetch a set of logs and related transaction inputs, the user must make N+1 RPC requests (one to fetch logs, then one per unique transaction).
- **Field selection.** Every RPC method returns a fixed object schema. Users that only need block number and timestamp have no choice but to fetch large unrelated fields like `logsBloom`, only to immediately discard them.
- **Pagination.** The `eth_getLogs` pagination design causes frequent timeouts and client-side workarounds. The RPC methods for blocks, transactions, and traces don't support range queries at all.

These shortcomings impose unnecessary compute, memory, and bandwidth costs on both users and node operators.

## Example

This request uses the `eth_queryLogs` method to fetch `Transfer` event logs emitted by the USDC contract on Monad mainnet, including the timestamp of each log's parent block.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "eth_queryLogs",
  "params": [{
    "filter": {
      "address": "0x754704Bc059F8C67012fEd69BC8A327a5aafb603",
      "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]
    },
    "fields": {
      "logs": ["blockNumber", "logIndex", "address", "data", "topics"],
      "blocks": ["number", "timestamp"]
    },
    "order": "asc",
    "fromBlock": "0x5E69EC4",
    "toBlock": "0x5E69ECB"
  }]
}
```

The response includes the specified fields for each matched log and related block, and resolved block references for `fromBlock`, `toBlock`, and `cursorBlock`.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "data": {
      "logs": [
        {
          "blockNumber": "0x5E69EC6",
          "logIndex": "0x4F",
          "address": "0x754704Bc059F8C67012fEd69BC8A327a5aafb603",
          "data": "0x000000000000000000000000000000000000000000000000000000000432d69f",
          "topics": [
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            "0x000000000000000000000000928dc8afe312df45576b15b08c086c5427fd8207",
            "0x000000000000000000000000d6aeaa631c867347afacf038cb3be58ca5c9cedf"
          ]
        },
        {
          "blockNumber": "0x5E69EC6",
          "logIndex": "0x57",
          "address": "0x754704Bc059F8C67012fEd69BC8A327a5aafb603",
          "data": "0x0000000000000000000000000000000000000000000000000000000003f87ab2",
          "topics": [
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            "0x000000000000000000000000928dc8afe312df45576b15b08c086c5427fd8207",
            "0x0000000000000000000000009bbc4b5339f7a24ae4548bd923c36aebc5e7c870"
          ]
        }
      ],
      "blocks": [
        {
          "number": "0x5E69EC6",
          "timestamp": "0x6a8d5688"
        }
      ]
    },
    "fromBlock": {
      "number": "0x5E69EC4",
      "hash": "0x93c7d639e007fd25626e326ad7a8a20977d6c0e3ab9da32c81ae7ec1d39577d8",
      "parentHash": "0xcb3a39ea3177e88617c2ad5a48e0922277638fe0ce08f0548b7f639e90894b58"
    },
    "toBlock": {
      "number": "0x5E69ECB",
      "hash": "0x323e8aaf8d9b65afc6d7e3d0d589dac6b2d4050af146b7a1bd7226df604c4587",
      "parentHash": "0xd1b683ccca914f70da48d36031f3c1332c0d3af8af1dc5a82ecbd19d8e6ec3d8"
    },
    "cursorBlock": {
      "number": "0x5E69ECB",
      "hash": "0x323e8aaf8d9b65afc6d7e3d0d589dac6b2d4050af146b7a1bd7226df604c4587",
      "parentHash": "0xd1b683ccca914f70da48d36031f3c1332c0d3af8af1dc5a82ecbd19d8e6ec3d8"
    }
  }
}
```

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Conventions

#### Value types

This document uses the value type conventions of the Ethereum JSON-RPC interface:

| Type | Encoding | Examples |
| --- | --- | --- |
| `QUANTITY` | An unsigned integer, encoded as a `0x`-prefixed, big-endian hexadecimal string with no leading zeroes. Zero MUST be encoded as `"0x0"`. | `"0x0"`, `"0x5E69EC6"` |
| `DATA` | A byte sequence, encoded as a `0x`-prefixed hexadecimal string with two hex digits per byte, and therefore an even number of digits. The empty byte sequence MUST be encoded as `"0x"`. | `"0x"`, `"0x0f3a"` |
| `TAG` | One of the block tag strings accepted by `fromBlock` and `toBlock`; see [Block range](#block-range). | `"latest"`, `"finalized"` |

All other types named in this document (`string`, `number`, `boolean`, `object`, and array forms such as `DATA[]`, `number[]`, and `string[]`) are the corresponding JSON types.

#### Field availability

Each method's response table has an Availability column describing when a field is present in an object.

| Value | Meaning |
| --- | --- |
| Required | Present in every object of that type. |
| Fork-dependent | Present only when the feature that introduced the field is active for the block being returned. |
| Type-dependent | Present only for the transaction types that carry the field, such as `maxFeePerGas` on EIP-1559 transactions. |
| Optional | MAY be absent even when selected, either because it does not apply to the object — `error` on a call trace that succeeded, for example — or because the server does not populate it. |

### Request and response

#### Request

 For all methods, `params` MUST be a single-element array whose first element is the request object defined below.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `fromBlock` | `QUANTITY` or `TAG` | No | Inclusive range start. See [Block range](#block-range). |
| `toBlock` | `QUANTITY` or `TAG` | No | Inclusive range end. See [Block range](#block-range). |
| `order` | `string` | No | Traversal direction, `asc` (default) or `desc`. See [Block range](#block-range). |
| `target` | `QUANTITY` | No | Target number of primary objects per page. See [Block-aligned pagination](#block-aligned-pagination). |
| `filter` | `object` | No | Method-specific filter object. See [Filters](#filters) and each method's Filter section. |
| `fields` | `object` | No | Method-specific selection of fields to include and relations to join. See [Fields and relations](#fields-and-relations) and each method's Fields section. |

#### Response

| Field | Type | Description |
| --- | --- | --- |
| `data` | `object` | Method-specific query result object, keyed by object name. Each value is an array of objects containing the requested fields. |
| `fromBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The resolved starting block at query execution time. If `fromBlock` in the request was a tag, this reflects the block that tag resolved to. |
| `toBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The resolved ending block at query execution time. If `toBlock` was `"latest"` or omitted in `asc` mode, this reflects the block the node considered latest at query execution time. |
| `cursorBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The final block in the page (inclusive). The response contains every matching primary object from `fromBlock` through `cursorBlock`. See [Block-aligned pagination](#block-aligned-pagination). |

### Query semantics

#### Block range

Each request scans a contiguous, inclusive range of blocks from `fromBlock` to `toBlock`, in the direction given by `order`:

- `asc` (default): scan from `fromBlock` upward, returning results oldest-first. `fromBlock` is the lower bound and `toBlock` the upper bound.
- `desc`: scan from `fromBlock` downward, returning results newest-first. `fromBlock` is the upper bound and `toBlock` the lower bound.

`fromBlock` and `toBlock` each accept a hex-encoded block number (for example `"0xF4240"`) or a tag: `"latest"`, `"earliest"`, `"safe"`, `"finalized"`. Tags MUST be resolved server-side at query execution time. If omitted, `fromBlock` defaults to `"earliest"` in `asc` mode or `"latest"` in `desc` mode, and `toBlock` defaults to `"latest"` in `asc` mode or `"earliest"` in `desc` mode. An `asc` scan with `toBlock` omitted therefore runs to chain tip, and a `desc` scan with `toBlock` omitted runs to genesis.

A resolved range is inverted if `fromBlock` is greater than `toBlock` in `asc` mode, or less than `toBlock` in `desc` mode. The server MUST fail a request with an inverted range with `-32602`.

A node is not required to hold the entire chain history. Each method has an *availability window*: the contiguous range of blocks for which that node can serve that method's objects. The window MAY differ between methods on the same node, since a node may retain every block back to genesis while retaining traces only for recent history.

After resolving `fromBlock` and `toBlock` to block numbers, the server MUST compare the resolved range against the availability window for the method being called. If any block in that range falls outside the window — whether because the data was pruned, was never indexed, or the block does not yet exist — the server MUST fail the request with `-32001` rather than returning a truncated result.

#### Block-aligned pagination

Each response covers a *page*: a contiguous run of blocks from `fromBlock` through `cursorBlock` in traversal order. Pages are block-aligned: the response contains every matching primary object from every block in the page, and none from blocks outside it. A page never contains part of a block.

The `target` request field sets the target number of primary objects per page. It MUST be at least `0x1`, and related objects MUST NOT count toward it.

The server builds a page by scanning the resolved range one block at a time, starting at `fromBlock`, and ends the page at the first of the following conditions:

1. **Range end.** The scan reaches `toBlock`. `cursorBlock` is `toBlock`, and no blocks remain.
2. **Target reached.** The scan reaches a block that brings the page's primary object count to `target` or greater. `cursorBlock` MUST be set to this final block, and the response MUST include every matching primary object in it, even if the count then exceeds `target`. This condition does not apply if `target` is omitted.
3. **Budget reached.** The server exhausts its *budget* — any server-imposed bound on the work or size of a single response, such as execution time, response size, or number of primary objects — before completing a block. The server MUST discard that block's partial results and end the page at the previous block.

Every successful response MUST include at least the `fromBlock` block, so each page advances by at least one block. If the server exhausts its budget before completing `fromBlock`, no block-aligned page exists, and the server MUST fail the request with `-32005`. Once the server has completed at least one block, it MUST return the page rather than fail with `-32005`.

As a result, a page contains more than `target` primary objects when its final block holds more matches than needed, and fewer — possibly zero — when the range ends or the budget is reached first. The number of primary objects in a response therefore does not indicate whether more data remains; only `cursorBlock` does.

For example, consider an `asc` request with `fromBlock` 10, `toBlock` 20, and `target` 100 (decimal for readability), where blocks 10 through 13 contain 40, 0, 55, and 30 matching primary objects:

| Scenario | Ending condition | `cursorBlock` | Primary objects returned |
| --- | --- | --- | --- |
| Budget not exhausted | Target reached at block 13 (40 + 0 + 55 + 30 = 125) | 13 | 125 |
| Budget exhausted while scanning block 13 | Budget reached | 12 | 95 |
| Budget exhausted while scanning block 10 | — | — | Request fails with `-32005` |

#### Chain consistency

Every object and block reference in a response MUST come from the same canonical chain, as seen by the server at query execution time. A response MUST NOT mix blocks from before and after a reorg.

This guarantee applies within a single response. Consecutive pages MAY reflect different chains if a reorg occurs between requests; see [Reorg detection](#reorg-detection).

#### Filters

Each method defines its own set of filter fields; see that method's Filter section. The rules below apply to all of them.

All conditions within a `filter` object are combined with AND semantics. Except where a method's Filter section states otherwise, each filter field accepts either a single value or an array of values; an array matches if the field equals any element of the array (OR within the field). An omitted filter field places no constraint on the result. If `filter` is omitted, every object of the method's primary type within the block range is returned.

#### Fields and relations

The `fields` object selects what the response includes. Each key names an object schema, and each value is either an array of field names to include from that schema or the string `"all"` to include every field of that schema. The key naming the method's primary object type selects fields on the primary objects; every other key names a relation to join. If `fields` is omitted, all fields of the primary object are included and no relations are joined. See each method's Fields section for the keys it accepts.

A relation is a reference from a primary object to a single object of another type. Only many-to-one relations are joinable. Each method MUST reject a `fields` key that names a relation it does not support.

Results MUST be returned in normalized form. Related objects appear under `data` in their own array, keyed by the same name that selected them in `fields`. A related array MUST contain only objects referenced by a primary object in the same response, and a related object referenced by more than one primary object MUST appear only once.

Related objects use the schema defined in the response section of the corresponding method: `blocks` objects as defined under `eth_queryBlocks`, and `transactions` objects as defined under `eth_queryTransactions`.

#### Ordering

Each object type has an ordering key, defined in the Ordering section of the method that returns it as its primary type. The primary and related object arrays in `data` MUST be sorted by these ordering keys — ascending in `asc` mode and descending in `desc` mode. The sort applies across the entire array, not only at block granularity: in `desc` mode the objects within a single block are returned in reverse order as well.

### `eth_queryBlocks`

Query for block headers.

#### Filter

| Field | Accepted Type | Description |
| --- | --- | --- |
| `miner` | `DATA` or `DATA[]` | Block miner / coinbase address. |

#### Fields

| Key | Type | Description |
| --- | --- | --- |
| `blocks` | `string[]` or `"all"` | Primary. Fields to include from the `blocks` schema. |

`eth_queryBlocks` supports no relations.

#### Response

| Field | Type | Description | Availability |
| --- | --- | --- | --- |
| `number` | `QUANTITY` | Block number. | Required |
| `hash` | `DATA` | Block hash. | Required |
| `parentHash` | `DATA` | Parent block hash. | Required |
| `timestamp` | `QUANTITY` | Block timestamp. | Required |
| `nonce` | `DATA` | Block nonce. | Required |
| `sha3Uncles` | `DATA` | Ommers hash. | Required |
| `logsBloom` | `DATA` | Logs bloom filter. | Required |
| `transactionsRoot` | `DATA` | Transactions root. | Required |
| `stateRoot` | `DATA` | State root. | Required |
| `receiptsRoot` | `DATA` | Receipts root. | Required |
| `miner` | `DATA` | Coinbase address. | Required |
| `difficulty` | `QUANTITY` | Block difficulty. | Fork-dependent |
| `totalDifficulty` | `QUANTITY` | Total difficulty of the chain up to this block. | Fork-dependent |
| `extraData` | `DATA` | Extra data. | Required |
| `size` | `QUANTITY` | Block size. | Required |
| `gasLimit` | `QUANTITY` | Block gas limit. | Required |
| `gasUsed` | `QUANTITY` | Gas used by transactions in the block. | Required |
| `baseFeePerGas` | `QUANTITY` | Base fee per gas. | Fork-dependent |
| `blobGasUsed` | `QUANTITY` | Blob gas used. | Fork-dependent |
| `excessBlobGas` | `QUANTITY` | Excess blob gas. | Fork-dependent |
| `withdrawalsRoot` | `DATA` | Withdrawals root. | Fork-dependent |
| `parentBeaconBlockRoot` | `DATA` | Parent beacon block root. | Fork-dependent |

#### Ordering

Block objects are ordered by `number`.

### `eth_queryTransactions`

Query for transactions included in blocks.

#### Filter

| Field | Accepted Type | Description |
| --- | --- | --- |
| `from` | `DATA` or `DATA[]` | Sender address. |
| `to` | `DATA` or `DATA[]` | Recipient address. |
| `selector` | `DATA` or `DATA[]` | 4-byte function selector (first 4 bytes of `input`). Transactions with `input` shorter than 4 bytes MUST NOT match a `selector` filter. |

#### Fields

| Key | Type | Description |
| --- | --- | --- |
| `transactions` | `string[]` or `"all"` | Primary. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `"all"` | Relation. Fields to include from the `blocks` schema. |

#### Response

The `transactions` objects combine transaction fields with receipt fields. The receipt `logs` field is not included.

| Field | Type | Description | Availability |
| --- | --- | --- | --- |
| `hash` | `DATA` | Transaction hash. | Required |
| `blockHash` | `DATA` | Hash of the containing block. | Required |
| `blockNumber` | `QUANTITY` | Number of the containing block. | Required |
| `transactionIndex` | `QUANTITY` | Transaction index in the block. | Required |
| `from` | `DATA` | Sender address. | Required |
| `to` | `DATA` or `null` | Recipient address, or `null` for contract creation. | Required |
| `nonce` | `QUANTITY` | Sender nonce. | Required |
| `input` | `DATA` | Calldata. | Required |
| `value` | `QUANTITY` | Transferred value. | Required |
| `gas` | `QUANTITY` | Gas limit. | Required |
| `gasPrice` | `QUANTITY` | Gas price for legacy and EIP-2930 transactions. | Type-dependent |
| `type` | `QUANTITY` | Transaction type, such as `0x0` or `0x2`. | Required |
| `chainId` | `QUANTITY` | Chain ID. | Type-dependent |
| `accessList` | `object[]` | Access list for typed transactions. | Type-dependent |
| `maxFeePerGas` | `QUANTITY` | EIP-1559 maximum fee per gas. | Type-dependent |
| `maxPriorityFeePerGas` | `QUANTITY` | EIP-1559 maximum priority fee. | Type-dependent |
| `maxFeePerBlobGas` | `QUANTITY` | Maximum blob fee per gas. | Fork-dependent |
| `blobVersionedHashes` | `DATA[]` | Versioned blob hashes. | Fork-dependent |
| `v` | `QUANTITY` | ECDSA signature recovery value. | Required |
| `yParity` | `QUANTITY` | ECDSA signature parity for typed transactions. | Type-dependent |
| `r` | `DATA` | ECDSA signature `r` value. | Required |
| `s` | `DATA` | ECDSA signature `s` value. | Required |
| `blockTimestamp` | `QUANTITY` | Timestamp of the containing block. | Optional |
| `contractAddress` | `DATA` or `null` | Created contract address, or `null`. | Required |
| `cumulativeGasUsed` | `QUANTITY` | Cumulative gas used in the block. | Required |
| `gasUsed` | `QUANTITY` | Gas used by the transaction. | Required |
| `effectiveGasPrice` | `QUANTITY` | Effective gas price paid. | Required |
| `logsBloom` | `DATA` | Receipt logs bloom filter. | Required |
| `status` | `QUANTITY` | `0x1` for success or `0x0` for reverted. | Required |
| `root` | `DATA` | Post-state root. | Fork-dependent |
| `blobGasUsed` | `QUANTITY` | Blob gas used. | Fork-dependent |
| `blobGasPrice` | `QUANTITY` | Blob gas price. | Fork-dependent |

#### Ordering

Transaction objects are ordered by `(blockNumber, transactionIndex)`.

### `eth_queryLogs`

Query for event logs emitted during transaction execution.

#### Filter

`topics` does not follow the general array rule; see below.

| Field | Accepted Type | Description |
| --- | --- | --- |
| `address` | `DATA` or `DATA[]` | Contract address that emitted the log. |
| `topics` | see below | Positional topic filter. |

The `topics` filter MUST follow the same matching semantics as `eth_getLogs`. The value is an array of up to 4 positional entries. Each entry may be:

- A single topic hash (`DATA`): matches logs where `topics[i]` equals that hash.
- An array of topic hashes (`DATA[]`): matches logs where `topics[i]` equals any hash in the array.
- `null`: wildcard — matches any value at position `i`.

Trailing `null` entries MAY be omitted.

#### Fields

| Key | Type | Description |
| --- | --- | --- |
| `logs` | `string[]` or `"all"` | Primary. Fields to include from the `logs` schema. |
| `transactions` | `string[]` or `"all"` | Relation. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `"all"` | Relation. Fields to include from the `blocks` schema. |

#### Response

| Field | Type | Description | Availability |
| --- | --- | --- | --- |
| `address` | `DATA` | Address that emitted the log. | Required |
| `blockHash` | `DATA` | Hash of the containing block. | Required |
| `blockNumber` | `QUANTITY` | Number of the containing block. | Required |
| `blockTimestamp` | `QUANTITY` | Timestamp of the containing block. | Optional |
| `transactionHash` | `DATA` | Hash of the containing transaction. | Required |
| `transactionIndex` | `QUANTITY` | Transaction index in the block. | Required |
| `logIndex` | `QUANTITY` | Log index in the block, matching `eth_getLogs`. | Required |
| `topics` | `DATA[]` | Indexed event topics. | Required |
| `data` | `DATA` | Non-indexed event data. | Required |
| `removed` | `boolean` | Whether the log was removed by a reorg. Always `false` in these responses, since results are read from the canonical chain; retained for compatibility with `eth_getLogs` consumers. | Required |

#### Ordering

Log objects are ordered by `(blockNumber, logIndex)`.

### `eth_queryTraces`

Query for internal call traces.

#### Filter

`isTopLevel` accepts only a single boolean; the other fields follow the general array rule.

| Field | Accepted Type | Description |
| --- | --- | --- |
| `from` | `DATA` or `DATA[]` | Sender address. |
| `to` | `DATA` or `DATA[]` | Recipient address. |
| `selector` | `DATA` or `DATA[]` | 4-byte function selector (first 4 bytes of `input`). Traces with `input` shorter than 4 bytes MUST NOT match a `selector` filter. |
| `isTopLevel` | `boolean` | If `true`, only top-level traces (those with an empty `traceAddress`) are returned; if `false`, only traces made by an internal call (those with a non-empty `traceAddress`). If omitted, both are returned. |

#### Fields

| Key | Type | Description |
| --- | --- | --- |
| `traces` | `string[]` or `"all"` | Primary. Fields to include from the `traces` schema. |
| `transactions` | `string[]` or `"all"` | Relation. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `"all"` | Relation. Fields to include from the `blocks` schema. |

#### Response

Trace objects are flattened `callTracer` frames, omitting nested calls and trace logs.

| Field | Type | Description | Availability |
| --- | --- | --- | --- |
| `type` | `string` | Call type: `CALL`, `CALLCODE`, `DELEGATECALL`, `STATICCALL`, `CREATE`, `CREATE2`, or `SELFDESTRUCT`. | Required |
| `from` | `DATA` | Address initiating the call. | Required |
| `to` | `DATA` | Target address receiving the call. | Optional |
| `value` | `QUANTITY` | Amount of native token transferred. | Optional |
| `gas` | `QUANTITY` | Gas provided for the call. | Required |
| `gasUsed` | `QUANTITY` | Gas used during the call. | Required |
| `input` | `DATA` | Call data. | Required |
| `output` | `DATA` | Return data. | Optional |
| `error` | `string` | Call failure information. | Optional |
| `revertReason` | `string` | Solidity revert reason. | Optional |
| `blockHash` | `DATA` | Hash of the containing block. | Required |
| `blockNumber` | `QUANTITY` | Number of the containing block. | Required |
| `transactionHash` | `DATA` | Hash of the containing transaction. | Required |
| `transactionIndex` | `QUANTITY` | Transaction index in the block. | Required |
| `traceAddress` | `number[]` | Path through the nested call tree. | Required |
| `status` | `QUANTITY` | `0x1` for success or `0x0` for reverted. | Required |

#### Ordering

 Trace objects are ordered by `(blockNumber, transactionIndex, traceAddress)`, where `traceAddress` is compared lexicographically (element-wise), with shorter arrays sorting before longer arrays when one is a prefix of the other.

### `eth_queryTransfers`

Query for native token transfers. A transfer is any call frame whose `value` is greater than zero. The set of transfers in a block range is therefore exactly the subset of the traces in that range for which `value > 0`, and each transfer object carries the same trace context as the corresponding `eth_queryTraces` object.

#### Filter

`isTopLevel` accepts only a single boolean; the other fields follow the general array rule.

| Field | Accepted Type | Description |
| --- | --- | --- |
| `from` | `DATA` or `DATA[]` | Address initiating the transfer. |
| `to` | `DATA` or `DATA[]` | Address receiving the transfer. |
| `isTopLevel` | `boolean` | If `true`, only top-level transfers (those with an empty `traceAddress`) are returned; if `false`, only transfers made by an internal call (those with a non-empty `traceAddress`). If omitted, both are returned. |

#### Fields

| Key | Type | Description |
| --- | --- | --- |
| `transfers` | `string[]` or `"all"` | Primary. Fields to include from the `transfers` schema. |
| `transactions` | `string[]` or `"all"` | Relation. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `"all"` | Relation. Fields to include from the `blocks` schema. |

#### Response

Transfer objects have the same fields as the `eth_queryTraces` response, except that `to` and `value` are Required rather than Optional.

| Field | Type | Description | Availability |
| --- | --- | --- | --- |
| `type` | `string` | Call type that produced the transfer. | Required |
| `from` | `DATA` | Address initiating the transfer. | Required |
| `to` | `DATA` | Target address receiving the transfer. | Required |
| `value` | `QUANTITY` | Amount of native token transferred. | Required |
| `gas` | `QUANTITY` | Gas provided for the call. | Required |
| `gasUsed` | `QUANTITY` | Gas used during the call. | Required |
| `input` | `DATA` | Call data. | Required |
| `output` | `DATA` | Return data. | Optional |
| `error` | `string` | Call failure information. | Optional |
| `revertReason` | `string` | Solidity revert reason. | Optional |
| `blockHash` | `DATA` | Hash of the containing block. | Required |
| `blockNumber` | `QUANTITY` | Number of the containing block. | Required |
| `transactionHash` | `DATA` | Hash of the containing transaction. | Required |
| `transactionIndex` | `QUANTITY` | Transaction index in the block. | Required |
| `traceAddress` | `number[]` | Path through the nested call tree. | Required |
| `status` | `QUANTITY` | `0x1` for success or `0x0` for reverted. | Required |

#### Ordering

Transfer objects are ordered by `(blockNumber, transactionIndex, traceAddress)`, where `traceAddress` is compared element-wise.

### Errors

The methods use standard JSON-RPC error codes plus application-specific codes that follow the conventions established by EIP-1474. The codes whose boundaries matter for these methods are:

| Code | Message | Description |
| --- | --- | --- |
| `-32601` | Method not found | The node does not recognize the method, because it runs software that predates this MIP. This is the standard JSON-RPC code and is listed here only to distinguish it from `-32004`. |
| `-32004` | Method not supported | The node recognizes the method but is not configured to serve it, and so cannot serve it for any block range. A node that does not index traces, for example, returns this code for `eth_queryTraces` and `eth_queryTransfers` while still serving the other three methods. |
| `-32602` | Invalid params | Malformed request: unknown `fields` keys, invalid filter fields, a `fields` key naming an unrecognized or unsupported relation for this method, a `target` of `0x0`, or a block range that is inverted for the requested `order`. |
| `-32001` | Resource not found | The node serves this method, but the resolved block range falls partly or wholly outside its availability window for the method. See [Block range](#block-range). |
| `-32005` | Limit exceeded | The request exceeded a server-imposed resource limit. For the response budget, this occurs only when `fromBlock` alone exceeds the budget; see [Block-aligned pagination](#block-aligned-pagination). |

Example `-32005` error response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32005,
    "message": "Limit exceeded",
    "data": "Execution time greater than 5 seconds"
  }
}
```

## Usage

This section is informative. It describes recommended client behavior for these methods and introduces no requirements.

### Pagination

Each response is a page covering `fromBlock` through `cursorBlock`, inclusive; see [Block-aligned pagination](#block-aligned-pagination). If `cursorBlock.number` equals `toBlock.number`, the query is complete. Otherwise more blocks remain, regardless of how many primary objects the page contains: a page cut short by the server's budget can hold fewer than `target` objects, or none, and still not be the last.

To fetch the next page, the client should repeat the request with every parameter unchanged except `fromBlock`:

- `asc` mode: `fromBlock` = `cursorBlock.number + 1`
- `desc` mode: `fromBlock` = `cursorBlock.number - 1`

Because pages never split a block, resuming from the block after `cursorBlock` neither repeats nor skips objects, and clients do not need to reconcile partial blocks.

### Reorg detection

Blocks near the chain tip can be replaced by a chain reorganization, which may invalidate data that a client has already processed. Clients paging toward the tip in `asc` mode can cheaply detect this by comparing each page's `fromBlock.parentHash` with the previous page's `cursorBlock.hash`:

- **Match**: If the hashes match, the chain is unchanged. The client can safely process the new page.
- **Mismatch**: If the hashes do not match, a reorg has replaced the stored block or one of its ancestors. The client should stop appending and run the recovery procedure below.

### Reorg recovery

The recovery procedure finds the newest block the client processed that is still canonical, discards the data above it, and resumes paging from there.

This requires the client to retain a `number` and `hash` for every block it has processed at or after the block that `"finalized"` resolves to. Because a reorg cannot replace a finalized block, one of these references always matches, so the procedure always terminates.

1. Query `eth_queryBlocks` with `order: "desc"`, `fromBlock` set to `"latest"`, `toBlock` set to the oldest retained block number, and `fields` set to `{"blocks": ["number", "hash"]}`.
2. Walk the returned blocks newest to oldest. The first block whose `hash` matches the retained reference at the same block number is the recovery point.
3. Discard all stored data above the recovery point, drop the retained references above it, and resume paging from `recoveryPoint + 1`.

Setting `fromBlock` to `"latest"` rather than to the block number where detection failed keeps the query valid if the reorg shortened the chain.

### Joining relations

To associate a primary object with its related objects, the client should match a *join key* on the primary object against the corresponding field on the related object. The join condition for each supported relation is:

| Primary type | Join `blocks` | Join `transactions` |
| --- | --- | --- |
| `blocks` | — | — |
| `transactions` | `transactions.blockNumber == blocks.number` | — |
| `logs` | `logs.blockNumber == blocks.number` | `logs.transactionHash == transactions.hash` |
| `traces` | `traces.blockNumber == blocks.number` | `traces.transactionHash == transactions.hash` |
| `transfers` | `transfers.blockNumber == blocks.number` | `transfers.transactionHash == transactions.hash` |

Join keys are selected like any other field. A client that requests a relation should include both sides of its join key in `fields`; otherwise, the response has no way to indicate which related object belongs to which primary object.

The [Example](#example) request selects `blockNumber` on logs and `number` on blocks for this reason. Both returned logs have a `blockNumber` of `0x5E69EC6`, so both join to the single `blocks` object whose `number` is `0x5E69EC6`, and both logs have a block timestamp of `0x6a8d5688`. The block appears once even though two logs reference it. Blocks in the range that contain no matching logs, such as `0x5E69EC4`, do not appear at all.

## Rationale

**JSON-RPC interface.** These methods extend the existing JSON-RPC interface rather than introduce a new transport or query language. Node operators and client libraries can adopt them without new infrastructure, and existing tooling such as authentication, load balancing, and retries works unchanged.

**`eth_` namespace.** The methods use the `eth_` namespace because nothing in the interface is specific to Monad. They query objects common to every EVM chain — blocks, transactions, logs, traces, and transfers — and reuse the value types, block tags, and error code conventions of existing `eth_` methods.

**Block range and traversal direction.** Chain history is ordered by block, so a contiguous block range is the natural unit for scanning and resuming a query. Supporting both `asc` and `desc` lets the same method serve forward scans, such as backfilling an index from genesis, and backward scans, such as fetching the most recent N events from `"latest"`, without the client guessing a block window and widening it until enough results arrive.

**Block-aligned pagination.** The block is the atomic unit of chain history: a reorg replaces whole blocks, and indexers typically commit and roll back data one block at a time. The downside is that page size cannot be a hard limit. A page must include all of its final block, so the final block can push a page past `target`. For the same reason, if a single block has more matches than the server's budget allows, the server cannot return that block at all.

**Block references instead of an opaque cursor.** Because pages end on block boundaries, a block reference is a complete cursor. The response exposes it directly as `fromBlock`, `toBlock`, and `cursorBlock`, rather than wrapping it in an opaque token that would require either server-side state or an encoding shared by every implementation. With block numbers and hashes in every response, clients can resume pagination, check for completion, and detect reorgs without extra requests.

**Many-to-one relations only.** One-to-many relations, such as all transactions in a block, would make response sizes unpredictable, since a single block can contain thousands of transactions. Restricting relations to many-to-one, such as each log's parent block, guarantees that a response never contains more related objects of a given type than primary objects. For the same reason, related objects do not count toward `target`: their number is already bounded by the primary count, and counting them would make page boundaries depend on which relations the client requested.

**Normalized responses.** Related objects are returned in their own arrays, and each appears once even when several primary objects reference it. Embedding them instead would repeat the same block once for every log it contains. Separate arrays also match how clients typically store and index the data.

**Merged transactions and receipts.** `eth_queryTransactions` returns each transaction and its receipt as a single object. The standard interface splits them across `eth_getTransactionByHash` and `eth_getTransactionReceipt` because receipts are produced by execution rather than stored in the block body, a distinction that does not matter to clients. Many common queries need fields from both, such as filtering transactions by `to` and reading `status` to skip reverted calls.

## Backwards Compatibility

There are no backwards compatibility issues. These are five new JSON-RPC methods; no existing method's request or response shape is changed. Clients that do not support these methods are unaffected, and a node that does not recognize them responds with the standard JSON-RPC "method not found" error (`-32601`). A node that recognizes the methods but is not configured to serve all of them responds with `-32004` for the methods it does not serve; see [Errors](#errors).

## Security Considerations

These methods increase server-side workload by enabling high-volume historical queries. Implementations are expected to enforce request limits, such as a maximum response size or execution time, and to apply fair-use controls such as rate limiting and per-API-key quotas, to mitigate denial-of-service and cost-amplification risks.

Results near the chain tip are not final. A reorganization can invalidate pages a client has already consumed, so a client that persists query results needs a recovery strategy built on the block references in the response; see [Reorg detection](#reorg-detection).

Because the new RPC methods support joins and field projection, the worst-case work for a single request depends on the requested relations and fields as well as on the block range. Implementations should validate relations and fields strictly and bound that worst case.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
