---
mip: XX
title: JSON-RPC Query Methods
description: Five new JSON-RPC methods that enable efficient queries for raw chain history data
author: Kevin Koste (@typedarray), Kyle Scott (@kyscott18), Jay Miller, Andre Benedito
discussions-to:
status: Draft
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

All five methods share a common request and response shape. A request specifies a block range, a traversal order, a result limit, an optional filter, and an optional field selection that also controls which related objects are joined into the response. A response returns normalized, deduplicated result arrays keyed by object type, along with three block references that clients use for pagination and reorg detection.

## Motivation

The standard Ethereum JSON-RPC interface provides inadequate primitives for querying chain history. Many useful queries are simply not possible, and the queries that are supported suffer from overfetching and inefficient pagination.

This proposal aims to address four specific shortcomings.

- **Filtering.** The `eth_getLogs` method supports log filtering, but there is no way to filter transactions or traces. To query all transactions sent to a specific address, the user must fetch entire blocks and filter client-side.
- **Relations.** There is no way to join related objects in a single request. To fetch a set of logs and related transaction inputs, the user must make N+1 RPC requests (one to fetch logs, then one per unique transaction).
- **Field selection.** Every RPC method returns a fixed object schema. Users that only need block number and timestamp have no choice but to fetch large unrelated fields like `logsBloom`, only to immediately discard them.
- **Pagination.** The `eth_getLogs` pagination design causes frequent timeouts and client-side workarounds. The RPC methods for blocks, transactions, and traces don't support range queries at all.

These shortcomings impose unnecessary compute, memory, and bandwidth costs on both users and node operators.

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.html) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.html).

### Overview

Each of the proposed JSON-RPC methods follows the same request and response shape. Each method takes a single object parameter.

**Request.** Each request specifies a block range with `fromBlock` and `toBlock`, a traversal order (`"asc"` for oldest-first, `"desc"` for newest-first), and a `limit` on how many primary objects to return. Within that range, an optional `filter` narrows which objects are returned (for example, filtering logs by contract address and topic, or transactions by sender). An optional `fields` parameter controls which fields are returned for the primary objects and any related objects to join in the same response.

**Response.** The `data` object contains the matched results, keyed by object type (e.g. `"logs"`, `"blocks"`). The response also includes three block references (`fromBlock`, `toBlock`, and `cursorBlock`) which record the exact blocks the server used when executing the query. These are used for pagination and reorg detection.

**Pagination.** Because the server may stop before scanning the entire requested range (due to the `limit` or an internal constraint), `cursorBlock` records the last block scanned. To fetch the next page, submit a follow-up request starting one block past `cursorBlock`. Once `cursorBlock` equals `toBlock`, pagination is complete.

### Example

This request queries for `Transfer` events emitted by a token contract, including the timestamp of each log's parent block.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "eth_queryLogs",
  "params": [{
    "filter": {
      "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
      "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]
    },
    "fields": {
      "logs": ["blockNumber", "logIndex", "address", "data", "topics"],
      "blocks": ["number", "timestamp"]
    },
    "order": "asc",
    "fromBlock": "0xF4240",
    "toBlock": "0xF4E20",
    "limit": "0x1F4"
  }]
}
```

The response includes the specified fields for each matched log and related block, and block reference information for pagination and reorg detection.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "data": {
      "logs": [
        {
          "blockNumber": "0xF4290",
          "logIndex": "0x3",
          "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
          "data": "0x000000000000000000000000000000000000000000000000000000003b9aca00",
          "topics": [
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
            "0x000000000000000000000000ab5801a7d398351b8be11c439e05c5b3259aec9b"
          ]
        },
        {
          "blockNumber": "0xF4290",
          "logIndex": "0x7",
          "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
          "data": "0x000000000000000000000000000000000000000000000000000000000ee6b280",
          "topics": [
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            "0x000000000000000000000000ab5801a7d398351b8be11c439e05c5b3259aec9b",
            "0x0000000000000000000000004838b106fce9647bdf1e7877bf73ce8b0bad5f97"
          ]
        }
      ],
      "blocks": [
        {
          "number": "0xF4290",
          "timestamp": "0x679b8f20"
        }
      ]
    },
    "fromBlock": {
      "number": "0xF4240",
      "hash": "0x3d6122660cc824376f11ee842f83addc3525e2dd6756b9bcf0affa6aa88cf741",
      "parentHash": "0xb4f81f27f56f5059b00e4b9041fbd76dad1d6dc3b7cb1d0a7c58d09f91a1c7e2"
    },
    "toBlock": {
      "number": "0xF4E20",
      "hash": "0xa9f2d63b518e4a55b5982e3c7b33e9f13286b0a4c638b06a1f2a9d0d87b591c4",
      "parentHash": "0x1c7e4b5d09f281d7e3f19a6b7c8d2e5f7a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d"
    },
    "cursorBlock": {
      "number": "0xF4E20",
      "hash": "0xa9f2d63b518e4a55b5982e3c7b33e9f13286b0a4c638b06a1f2a9d0d87b591c4",
      "parentHash": "0x1c7e4b5d09f281d7e3f19a6b7c8d2e5f7a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d"
    }
  }
}
```

### Common Definitions

All five methods share a common request structure and response envelope. Method-specific fields are documented in each method's section below.

#### Value Types

This document uses the value type conventions of the Ethereum JSON-RPC interface:

- `QUANTITY` — an unsigned integer, encoded as a `0x`-prefixed, big-endian hexadecimal string with no leading zeroes. Zero MUST be encoded as `"0x0"`.
- `DATA` — a byte sequence, encoded as a `0x`-prefixed hexadecimal string with two hex digits per byte, and therefore an even number of digits. The empty byte sequence MUST be encoded as `"0x"`.
- `TAG` — one of the block tag strings accepted by `fromBlock` and `toBlock`; see the `fromBlock` row below.

All other types named in this document (`string`, `number`, `boolean`, `object`, and array forms such as `DATA[]`, `number[]`, and `string[]`) are the corresponding JSON types.

#### Request

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `filter` | `object` | No | Method-specific filter object. See each method's Filter section. |
| `fields` | `object` | No | Method-specific fields to include for primary and related objects. See each method's Fields section. |
| `order` | `string` | No | Traversal direction. `"asc"` (default): scan from `fromBlock` upward, returning results oldest-first; if `toBlock` is omitted, the scan runs to chain tip. `"desc"`: scan from `fromBlock` downward, returning results newest-first; if `toBlock` is omitted, the scan runs to genesis. |
| `fromBlock` | `QUANTITY` or `TAG` | No | Inclusive range start. In `"asc"` mode, the lower bound; in `"desc"` mode, the upper bound. Accepts a hex-encoded block number (e.g. `"0xF4240"`) or a tag: `"latest"`, `"earliest"`, `"safe"`, `"finalized"`. Tags MUST be resolved server-side at query execution time; see Block Range Availability for how `"earliest"` resolves. If omitted, defaults to `"earliest"` in `"asc"` mode or `"latest"` in `"desc"` mode. |
| `toBlock` | `QUANTITY` or `TAG` | No | Inclusive range end. In `"asc"` mode, the upper bound; in `"desc"` mode, the lower bound. Same value types as `fromBlock`. If omitted, defaults to `"latest"` in `"asc"` mode or `"earliest"` in `"desc"` mode. |
| `limit` | `QUANTITY` | No | Target number of primary objects to return. The server MAY return fewer if an internal constraint (e.g. response size or execution time) is reached, and MUST return more when needed to complete the current block. Related objects MUST NOT count toward this limit. If omitted, defaults to `100`. |

#### Response

| Field | Type | Description |
| --- | --- | --- |
| `data` | `object` | Method-specific query result object, keyed by object name. Each value is an array of objects containing the requested fields. |
| `fromBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The resolved starting block at query execution time. If `fromBlock` in the request was a tag, this reflects the block that tag resolved to. |
| `toBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The resolved ending block at query execution time. If `toBlock` was `"latest"` or omitted in `"asc"` mode, this reflects the block the node considered latest at query execution time. |
| `cursorBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The last block the server scanned (inclusive). The server MUST complete the current block before stopping, so all matching objects from this block are included in the response. |

Each method defines an ordering key over its primary objects; see that method's Response section. Primary objects MUST be sorted by that key — ascending in `"asc"` mode and descending in `"desc"` mode. The sort applies across the entire result array, not only at block granularity: in `"desc"` mode the primary objects within a single block are returned in reverse order as well.

Results MUST be returned in normalized form: primary objects and related objects appear in separate arrays under `data`, and a related object referenced by multiple primary objects MUST appear only once.

Only many-to-one relations are joinable. A method MUST reject a `fields` key that names a relation it does not support.

#### Errors

The methods use standard JSON-RPC error codes plus the following application-specific codes, which follow the conventions established by EIP-1474:

| Code | Message | Description |
| --- | --- | --- |
| `-32602` | Invalid params | Malformed request: unknown `fields` keys, invalid filter fields, `fields` references an unrecognized or unsupported relation for this method, etc. |
| `-32001` | Resource not found | The resolved block range falls partly or wholly outside the node's availability window for this method. See Block Range Availability below. |
| `-32004` | Method not supported | The node does not implement this method. A node that does not index traces, for example, MAY return this code for `eth_queryTraces` and `eth_queryTransfers` while still serving the other three methods. |
| `-32005` | Limit exceeded | The request exceeded a server-imposed resource limit. |

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

**Block Range Availability.**

A node is not required to hold the entire chain history. Each method has an *availability window*: the contiguous range of blocks for which that node can serve that method's objects. The window MAY differ between methods on the same node, since a node may retain every block back to genesis while retaining traces only for recent history.

After resolving `fromBlock` and `toBlock` to block numbers, the server MUST compare the resolved range against the availability window for the method being called. If any block in that range falls outside the window — whether because the data was pruned, was never indexed, or the block does not yet exist — the server MUST fail the request with `-32001` rather than returning a truncated result.

The `"earliest"` tag MUST resolve to the first block in the availability window for the method being called, which on an archive node is the genesis block. Together with `"latest"`, this guarantees that the default range is always servable.

### `eth_queryBlocks`

Query for block headers.

#### Request

`eth_queryBlocks` accepts all common request parameters (`order`, `fromBlock`, `toBlock`, and `limit`) and the following method-specific parameters.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `filter` | `object` | No | Filter object. See Filter below. If omitted, all blocks in the block range are returned. |
| `fields` | `object` | No | Fields to include in the response. See Fields below. If omitted, all `blocks` fields are included and no relations are joined. |

#### Filter

All conditions are combined with AND semantics. Each filter field accepts a single value or an array of values; an array matches if the value equals any element (OR within the field).

| Field | Accepted Type | Description |
| --- | --- | --- |
| `miner` | `DATA` or `DATA[]` | Block miner / coinbase address. |

#### Fields

The `fields` object accepts the following keys. The value is an array of field names to include, or `true` to include all fields.

| Key | Type | Description |
| --- | --- | --- |
| `blocks` | `string[]` or `true` | Fields to include from the `blocks` schema. |

`eth_queryBlocks` does not support any relations.

#### Response

`data` contains a single key, `blocks`. Rows are ordered by `number`. Availability describes whether a field is present in the row schema; field projection can still omit any field that is not selected in `fields`.

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

### `eth_queryTransactions`

Query for transactions included in blocks.

#### Request

`eth_queryTransactions` accepts all common request parameters (`order`, `fromBlock`, `toBlock`, and `limit`) and the following method-specific parameters.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `filter` | `object` | No | Filter object. See Filter below. If omitted, all transactions in the block range are returned. |
| `fields` | `object` | No | Fields to include in the response. See Fields below. If omitted, all `transactions` fields are included and no relations are joined. |

#### Filter

All conditions are combined with AND semantics. Each filter field accepts a single value or an array of values; an array matches if the value equals any element (OR within the field).

| Field | Accepted Type | Description |
| --- | --- | --- |
| `from` | `DATA` or `DATA[]` | Sender address. |
| `to` | `DATA` or `DATA[]` | Recipient address. |
| `selector` | `DATA` or `DATA[]` | 4-byte function selector (first 4 bytes of `input`). Transactions with `input` shorter than 4 bytes MUST NOT match a `selector` filter. |

#### Fields

The `fields` object accepts the following keys. Each value is an array of field names to include from that schema, or `true` to include all fields.

| Key | Type | Description |
| --- | --- | --- |
| `transactions` | `string[]` or `true` | Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `true` | Fields to include from the `blocks` schema for related objects. |

#### Response

The `transactions` rows combine transaction fields with receipt fields. The receipt `logs` field is not included. Rows are ordered by `(blockNumber, transactionIndex)`.

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
| `type` | `DATA` | Transaction type, such as `0x0` or `0x2`. | Required |
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

If requested, each related `blocks` row has the fields listed in the `eth_queryBlocks` response.

### `eth_queryLogs`

Query for event logs emitted during transaction execution.

#### Request

`eth_queryLogs` accepts all common request parameters (`order`, `fromBlock`, `toBlock`, and `limit`) and the following method-specific parameters.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `filter` | `object` | No | Filter object. See Filter below. If omitted, all logs in the block range are returned. |
| `fields` | `object` | No | Fields to include in the response. See Fields below. If omitted, all `logs` fields are included and no relations are joined. |

#### Filter

All conditions are combined with AND semantics.

| Field | Accepted Type | Description |
| --- | --- | --- |
| `address` | `DATA` or `DATA[]` | Contract address that emitted the log. Accepts a single address or an array (matches any). |
| `topics` | see below | Positional topic filter. |

The `topics` filter MUST follow the same matching semantics as `eth_getLogs`. The value is an array of up to 4 positional entries. Each entry may be:

- A single topic hash (`DATA`): matches logs where `topics[i]` equals that hash.
- An array of topic hashes (`DATA[]`): matches logs where `topics[i]` equals any hash in the array.
- `null`: wildcard — matches any value at position `i`.

Trailing `null` entries MAY be omitted.

#### Fields

The `fields` object accepts the following keys. Each value is an array of field names to include from that schema, or `true` to include all fields.

| Key | Type | Description |
| --- | --- | --- |
| `logs` | `string[]` or `true` | Fields to include from the `logs` schema. |
| `transactions` | `string[]` or `true` | Fields to include from the `transactions` schema for related objects. |
| `blocks` | `string[]` or `true` | Fields to include from the `blocks` schema for related objects. |

#### Response

Rows are ordered by `(blockNumber, transactionIndex, logIndex)`.

| Field | Type | Description | Availability |
| --- | --- | --- | --- |
| `address` | `DATA` | Address that emitted the log. | Required |
| `blockHash` | `DATA` | Hash of the containing block. | Required |
| `blockNumber` | `QUANTITY` | Number of the containing block. | Required |
| `blockTimestamp` | `QUANTITY` | Timestamp of the containing block. | Optional |
| `transactionHash` | `DATA` | Hash of the containing transaction. | Required |
| `transactionIndex` | `QUANTITY` | Transaction index in the block. | Required |
| `logIndex` | `QUANTITY` | Log index in the receipt. | Required |
| `topics` | `DATA[]` | Indexed event topics. | Required |
| `data` | `DATA` | Non-indexed event data. | Required |
| `removed` | `boolean` | Whether the log was removed by a reorg. | Required |

If requested, related `transactions` rows have the fields listed in the `eth_queryTransactions` response, and related `blocks` rows have the fields listed in the `eth_queryBlocks` response.

### `eth_queryTraces`

Query for internal call traces.

#### Request

`eth_queryTraces` accepts all common request parameters (`order`, `fromBlock`, `toBlock`, and `limit`) and the following method-specific parameters.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `filter` | `object` | No | Filter object. See Filter below. If omitted, all traces in the block range are returned. |
| `fields` | `object` | No | Fields to include in the response. See Fields below. If omitted, all `traces` fields are included and no relations are joined. |

#### Filter

All conditions are combined with AND semantics. Each filter field except `isTopLevel` accepts a single value or an array of values.

| Field | Accepted Type | Description |
| --- | --- | --- |
| `from` | `DATA` or `DATA[]` | Sender address. |
| `to` | `DATA` or `DATA[]` | Recipient address. |
| `selector` | `DATA` or `DATA[]` | 4-byte function selector (first 4 bytes of `input`). Traces with `input` shorter than 4 bytes MUST NOT match a `selector` filter. |
| `isTopLevel` | `boolean` | If `true`, only top-level traces (those with an empty `traceAddress`) are returned. |

#### Fields

The `fields` object accepts the following keys. Each value is an array of field names to include from that schema, or `true` to include all fields.

| Key | Type | Description |
| --- | --- | --- |
| `traces` | `string[]` or `true` | Fields to include from the `traces` schema. |
| `transactions` | `string[]` or `true` | Fields to include from the `transactions` schema for related objects. |
| `blocks` | `string[]` or `true` | Fields to include from the `blocks` schema for related objects. |

#### Response

Trace rows are flattened `callTracer` frames. They omit nested calls and trace logs. Rows are ordered by `(blockNumber, transactionIndex, traceAddress)`, where `traceAddress` is compared element-wise.

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

If requested, related `transactions` rows have the fields listed in the `eth_queryTransactions` response, and related `blocks` rows have the fields listed in the `eth_queryBlocks` response.

### `eth_queryTransfers`

Query for native token transfers. A transfer is any call frame whose `value` is greater than zero. The set of transfers in a block range is therefore exactly the subset of the traces in that range for which `value > 0`, and each transfer row carries the same trace context as the corresponding `eth_queryTraces` row.

#### Request

`eth_queryTransfers` accepts all common request parameters (`order`, `fromBlock`, `toBlock`, and `limit`) and the following method-specific parameters.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `filter` | `object` | No | Filter object. See Filter below. If omitted, all transfers in the block range are returned. |
| `fields` | `object` | No | Fields to include in the response. See Fields below. If omitted, all `transfers` fields are included and no relations are joined. |

#### Filter

All conditions are combined with AND semantics. Each filter field except `isTopLevel` accepts a single value or an array of values.

| Field | Accepted Type | Description |
| --- | --- | --- |
| `from` | `DATA` or `DATA[]` | Address initiating the transfer. |
| `to` | `DATA` or `DATA[]` | Address receiving the transfer. |
| `isTopLevel` | `boolean` | If `true`, only top-level transfers (those initiated directly by a transaction, not by an internal call) are returned. |

#### Fields

The `fields` object accepts the following keys. Each value is an array of field names to include from that schema, or `true` to include all fields.

| Key | Type | Description |
| --- | --- | --- |
| `transfers` | `string[]` or `true` | Fields to include from the `transfers` schema. |
| `transactions` | `string[]` or `true` | Fields to include from the `transactions` schema for related objects. |
| `blocks` | `string[]` or `true` | Fields to include from the `blocks` schema for related objects. |

#### Response

Transfer rows contain the trace context for a native-token value movement. Rows are ordered by `(blockNumber, transactionIndex, traceAddress)`, where `traceAddress` is compared element-wise.

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

If requested, related `transactions` rows have the fields listed in the `eth_queryTransactions` response, and related `blocks` rows have the fields listed in the `eth_queryBlocks` response.

## Usage

### Pagination

Every response includes a `cursorBlock` identifying the last block the server scanned (inclusive). To paginate, a client submits a follow-up request using `cursorBlock.number + 1` (in `"asc"` mode) or `cursorBlock.number - 1` (in `"desc"` mode) as `fromBlock`.

If a response has `cursorBlock.number == toBlock.number`, that is the final page for the specified block range.

### Reorg Detection

The `fromBlock` and `toBlock` block references in the response include `hash` and `parentHash` fields to enable reorg detection.

A client can retain `toBlock` and begin its next query at the same block number. If the returned `fromBlock.hash` differs from the retained hash, a reorganization has occurred. Alternatively, when the next query begins at the following block, its `fromBlock.parentHash` MUST match the retained hash.

To recover, the client re-queries recent requests in descending block-number order. When both `fromBlock` and `toBlock` have matching hashes, `toBlock` is a known safe checkpoint. Data after that checkpoint is unsafe and should be reverted. The block range covered by retained checkpoints bounds the supported recovery depth.

## Rationale

**JSON-RPC as the message format.** These methods extend the existing JSON-RPC interface rather than introducing a new transport or query language. This keeps the implementation footprint small for both node operators and client library authors, and allows existing tooling (authentication, load balancing, retries) to work without modification.

**Block range and traversal direction.** Scanning a contiguous block range is the natural primitive for chain history queries. Supporting both `"asc"` and `"desc"` traversal lets clients page through history in either direction — forward for backfill indexing, backward for "show me the most recent N events" patterns — without implementing custom range logic.

**Block-aligned responses.** Splitting the objects from a single block across two pages would create ambiguity: a client receiving a partial block cannot tell whether it has seen all matching objects for that block. Always completing the current block before stopping eliminates this edge case and makes pagination deterministic.

**Flexible limit.** Treating `limit` as a target rather than a hard upper bound allows the server to satisfy block alignment (which may require returning slightly more objects than requested) while still bounding response sizes. Servers may also return fewer objects than requested if an internal constraint such as a response size or execution time limit is reached.

**Only many-to-one joins.** Allowing one-to-many joins (e.g. including all transactions for a block) would make response sizes unpredictable — a single block could contain thousands of transactions. Restricting joins to many-to-one relations (e.g. including the parent block for each log) guarantees that the number of related objects is bounded by the number of primary objects, which keeps response sizes proportional to `limit`.

**Limit applies only to primary objects.** Counting related objects toward the limit would create confusing interactions between `limit`, `fields`, and the actual number of primary objects returned. Applying the limit only to the primary array makes behavior predictable regardless of which relations are requested.

**Normalized vs. denormalized responses.** Results are returned in normalized form: primary objects and related objects in separate arrays, with shared objects (e.g. a block referenced by multiple logs) deduplicated. This avoids redundant data in the response payload and matches how clients typically store and index the data.

**Block cursors.** The response includes three block references (`fromBlock`, `toBlock`, and `cursorBlock`) rather than an opaque cursor token. `fromBlock` and `toBlock` reflect the resolved block numbers at query execution time, which is necessary when tags like `"latest"` are used. `cursorBlock` identifies the last block scanned so clients can resume pagination and detect reorgs by comparing hashes across requests.

## Backwards Compatibility

No backward compatibility issues found. These are five new JSON-RPC methods; no existing method's request or response shape is changed. Clients that do not support these methods are unaffected, and a node that has not implemented them responds with the standard JSON-RPC "method not found" error (`-32601`).

## Security Considerations

These methods increase server-side workload by enabling high-volume historical queries. Implementations should enforce request limits (max block range, max limit, max execution time) and apply fair-use controls (rate limiting, per-API-key quotas) to mitigate denial-of-service and cost-amplification risks.

Clients must not assume results are final when querying near the chain tip. Reorgs can invalidate prior pages; clients should persist and compare the returned block references across pages and re-fetch when mismatches occur.

Because the API supports joins and field projection, implementations should validate the requested relations and fields strictly and bound the worst-case work per request.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
