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

The standard Ethereum JSON-RPC interface provides inadequate primitives for querying chain history. Many useful queries are not possible, and the queries that are supported suffer from overfetching and inefficient pagination.

This proposal aims to address four specific shortcomings.

- **Filtering.** The `eth_getLogs` method supports log filtering, but there is no way to filter transactions or traces. To query all transactions sent to a specific address, the user must fetch entire blocks and filter client-side.
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

### Common definitions

#### Value types

This document uses the value type conventions of the Ethereum JSON-RPC interface:

- `QUANTITY` — an unsigned integer, encoded as a `0x`-prefixed, big-endian hexadecimal string with no leading zeroes. Zero MUST be encoded as `"0x0"`.
- `DATA` — a byte sequence, encoded as a `0x`-prefixed hexadecimal string with two hex digits per byte, and therefore an even number of digits. The empty byte sequence MUST be encoded as `"0x"`.
- `TAG` — one of the block tag strings accepted by `fromBlock` and `toBlock`; see the `fromBlock` row below.

All other types named in this document (`string`, `number`, `boolean`, `object`, and array forms such as `DATA[]`, `number[]`, and `string[]`) are the corresponding JSON types.

#### Request

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `filter` | `object` | No | Method-specific filter object. See Filters below and each method's Filter section. If omitted, every object of the method's primary type within the block range is returned. |
| `fields` | `object` | No | Method-specific selection of fields to include and relations to join. See Fields below and each method's Fields section. If omitted, all fields of the primary object are included and no relations are joined. |
| `order` | `string` | No | Traversal direction. `"asc"` (default): scan from `fromBlock` upward, returning results oldest-first; if `toBlock` is omitted, the scan runs to chain tip. `"desc"`: scan from `fromBlock` downward, returning results newest-first; if `toBlock` is omitted, the scan runs to genesis. |
| `fromBlock` | `QUANTITY` or `TAG` | No | Inclusive range start. In `"asc"` mode, the lower bound; in `"desc"` mode, the upper bound. Accepts a hex-encoded block number (for example `"0xF4240"`) or a tag: `"latest"`, `"earliest"`, `"safe"`, `"finalized"`. Tags MUST be resolved server-side at query execution time. If omitted, defaults to `"earliest"` in `"asc"` mode or `"latest"` in `"desc"` mode. |
| `toBlock` | `QUANTITY` or `TAG` | No | Inclusive range end. In `"asc"` mode, the upper bound; in `"desc"` mode, the lower bound. Same value types as `fromBlock`. If omitted, defaults to `"latest"` in `"asc"` mode or `"earliest"` in `"desc"` mode. |
| `limit` | `QUANTITY` | No | Target number of primary objects to return. The server MAY return fewer if an internal constraint such as response size or execution time is reached, and MUST return more when needed to complete the current block. If completing the current block would itself exceed such a constraint, the server MUST fail the request with `-32005` rather than return a partial block. Related objects MUST NOT count toward this limit. |

#### Response

| Field | Type | Description |
| --- | --- | --- |
| `data` | `object` | Method-specific query result object, keyed by object name. Each value is an array of objects containing the requested fields. |
| `fromBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The resolved starting block at query execution time. If `fromBlock` in the request was a tag, this reflects the block that tag resolved to. |
| `toBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The resolved ending block at query execution time. If `toBlock` was `"latest"` or omitted in `"asc"` mode, this reflects the block the node considered latest at query execution time. |
| `cursorBlock` | `{ number: QUANTITY, hash: DATA, parentHash: DATA }` | The last block the server scanned (inclusive). The server MUST complete the current block before stopping, so all matching objects from this block are included in the response. |

#### Filters

Each method defines its own set of filter fields; see that method's Filter section. The rules below apply to all of them.

All conditions within a `filter` object are combined with AND semantics. Except where a method's Filter section states otherwise, each filter field accepts either a single value or an array of values; an array matches if the field equals any element of the array (OR within the field). An omitted filter field places no constraint on the result.

#### Fields

The `fields` object selects what the response includes. Each key names an object schema, and each value is either an array of field names to include from that schema or `true` to include every field of that schema. The key naming the method's primary object type selects fields on the primary objects; every other key names a relation to join. See each method's Fields section for the keys it accepts.

#### Relations

A relation is a reference from a primary object to a single object of another type, joined into the response by naming that type as a key in `fields`. Only many-to-one relations are joinable. Each method MUST reject a `fields` key that names a relation it does not support.

Results MUST be returned in normalized form. Related objects appear under `data` in their own array, keyed by the same name that selected them in `fields`. A related array MUST contain only objects referenced by a primary object in the same response, and a related object referenced by more than one primary object MUST appear only once.

Related objects use the schema defined in the response section of the corresponding method: `blocks` objects as defined under `eth_queryBlocks`, and `transactions` objects as defined under `eth_queryTransactions`.

#### Ordering

Each method defines an ordering key over its primary objects; see that method's Ordering section. Primary objects MUST be sorted by that key — ascending in `"asc"` mode and descending in `"desc"` mode. The sort applies across the entire result array, not only at block granularity: in `"desc"` mode the primary objects within a single block are returned in reverse order as well.

#### Field availability

Each method's response table has an Availability column describing when a field is present in an object.

| Value | Meaning |
| --- | --- |
| Required | Present in every object of that type. |
| Fork-dependent | Present only when the feature that introduced the field is active for the block being returned. |
| Type-dependent | Present only for the transaction types that carry the field, such as `maxFeePerGas` on EIP-1559 transactions. |
| Optional | MAY be absent even when selected, either because it does not apply to the object — `error` on a call trace that succeeded, for example — or because the server does not populate it. |

#### Block range availability

A node is not required to hold the entire chain history. Each method has an *availability window*: the contiguous range of blocks for which that node can serve that method's objects. The window MAY differ between methods on the same node, since a node may retain every block back to genesis while retaining traces only for recent history.

After resolving `fromBlock` and `toBlock` to block numbers, the server MUST compare the resolved range against the availability window for the method being called. If any block in that range falls outside the window — whether because the data was pruned, was never indexed, or the block does not yet exist — the server MUST fail the request with `-32001` rather than returning a truncated result.

#### Errors

The methods use standard JSON-RPC error codes plus application-specific codes that follow the conventions established by EIP-1474. The codes whose boundaries matter for these methods are:

| Code | Message | Description |
| --- | --- | --- |
| `-32601` | Method not found | The node does not recognize the method, because it runs software that predates this MIP. This is the standard JSON-RPC code and is listed here only to distinguish it from `-32004`. |
| `-32004` | Method not supported | The node recognizes the method but is not configured to serve it, and so cannot serve it for any block range. A node that does not index traces, for example, returns this code for `eth_queryTraces` and `eth_queryTransfers` while still serving the other three methods. |
| `-32602` | Invalid params | Malformed request: unknown `fields` keys, invalid filter fields, a `fields` key naming an unrecognized or unsupported relation for this method, or a block range that is inverted for the requested `order`. |
| `-32001` | Resource not found | The node serves this method, but the resolved block range falls partly or wholly outside its availability window for the method. See Block range availability above. |
| `-32005` | Limit exceeded | The request exceeded a server-imposed resource limit, including the case where completing a single block would exceed that limit. |

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

### `eth_queryBlocks`

Query for block headers.

#### Filter

| Field | Accepted Type | Description |
| --- | --- | --- |
| `miner` | `DATA` or `DATA[]` | Block miner / coinbase address. |

#### Fields

| Key | Type | Description |
| --- | --- | --- |
| `blocks` | `string[]` or `true` | Primary. Fields to include from the `blocks` schema. |

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
| `transactions` | `string[]` or `true` | Primary. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `true` | Relation. Fields to include from the `blocks` schema. |

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
| `logs` | `string[]` or `true` | Primary. Fields to include from the `logs` schema. |
| `transactions` | `string[]` or `true` | Relation. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `true` | Relation. Fields to include from the `blocks` schema. |

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
| `traces` | `string[]` or `true` | Primary. Fields to include from the `traces` schema. |
| `transactions` | `string[]` or `true` | Relation. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `true` | Relation. Fields to include from the `blocks` schema. |

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

Trace objects are ordered by `(blockNumber, transactionIndex, traceAddress)`, where `traceAddress` is compared element-wise.

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
| `transfers` | `string[]` or `true` | Primary. Fields to include from the `transfers` schema. |
| `transactions` | `string[]` or `true` | Relation. Fields to include from the `transactions` schema. |
| `blocks` | `string[]` or `true` | Relation. Fields to include from the `blocks` schema. |

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

## Usage

This section is informative and introduces no requirements of its own.

### Pagination

A response with `cursorBlock.number` different from `toBlock.number` is a partial page: the server stopped before the end of the requested range. The next page is retrieved by repeating the request with `fromBlock` set to `cursorBlock.number + 1` in `"asc"` mode, or `cursorBlock.number - 1` in `"desc"` mode, and all other parameters unchanged. A response whose `cursorBlock.number` equals `toBlock.number` is the final page for the requested range.

### Reorg detection

The block references in the response include `hash` and `parentHash` fields, which let a client detect a reorganization across requests.

A client retains the last block reference it consumed: `cursorBlock` for a response that stopped before the end of the range, and `toBlock` for a response that reached it — these are the same reference on a final page. When the next query begins at the block after the retained one, its `fromBlock.parentHash` matches the retained hash unless a reorganization has occurred. A client that prefers to re-query the retained block itself compares the new `fromBlock.hash` against the retained hash instead.

To recover, the client re-queries recent requests in descending block-number order. When both `fromBlock` and `toBlock` have matching hashes, `toBlock` is a known safe checkpoint, and data after that checkpoint is discarded and re-fetched. The block range covered by retained checkpoints bounds the supported recovery depth.

## Rationale

**JSON-RPC as the message format.** These methods extend the existing JSON-RPC interface rather than introducing a new transport or query language. This keeps the implementation footprint small for both node operators and client library authors, and allows existing tooling (authentication, load balancing, retries) to work without modification.

**Block range and traversal direction.** Scanning a contiguous block range is the natural primitive for chain history queries. Supporting both `"asc"` and `"desc"` traversal lets clients page through history in either direction — forward for backfill indexing, backward for "show me the most recent N events" patterns — without implementing custom range logic.

**Block-aligned responses.** Splitting the objects from a single block across two pages would create ambiguity: a client receiving a partial block cannot tell whether it has seen all matching objects for that block. Always completing the current block before stopping eliminates this edge case and makes pagination deterministic.

**Flexible limit.** Treating `limit` as a target rather than a hard upper bound allows the server to satisfy block alignment (which may require returning slightly more objects than requested) while still bounding response sizes. Servers can also return fewer objects than requested if an internal constraint such as a response size or execution time limit is reached.

**Only many-to-one joins.** Allowing one-to-many joins, such as including all transactions for a block, would make response sizes unpredictable — a single block could contain thousands of transactions. Restricting joins to many-to-one relations, such as including the parent block for each log, guarantees that the number of related objects is bounded by the number of primary objects, which keeps response sizes proportional to `limit`.

**Limit applies only to primary objects.** Counting related objects toward the limit would create confusing interactions between `limit`, `fields`, and the actual number of primary objects returned. Applying the limit only to the primary array makes behavior predictable regardless of which relations are requested.

**Normalized vs. denormalized responses.** Results are returned in normalized form: primary objects and related objects in separate arrays, with shared objects, such as a block referenced by multiple logs, deduplicated. This avoids redundant data in the response payload and matches how clients typically store and index the data.

**Block cursors.** The response includes three block references (`fromBlock`, `toBlock`, and `cursorBlock`) rather than an opaque cursor token. `fromBlock` and `toBlock` reflect the resolved block numbers at query execution time, which is necessary when tags like `"latest"` are used. `cursorBlock` identifies the last block scanned so clients can resume pagination and detect reorgs by comparing hashes across requests.

## Backwards Compatibility

No backward compatibility issues found. These are five new JSON-RPC methods; no existing method's request or response shape is changed. Clients that do not support these methods are unaffected, and a node that does not recognize them responds with the standard JSON-RPC "method not found" error (`-32601`). A node that recognizes the methods but is not configured to serve all of them responds with `-32004` for the methods it does not serve; see Errors.

## Security Considerations

These methods increase server-side workload by enabling high-volume historical queries. Implementations are expected to enforce request limits, such as a maximum response size or execution time, and to apply fair-use controls such as rate limiting and per-API-key quotas, to mitigate denial-of-service and cost-amplification risks.

Results near the chain tip are not final. A reorganization can invalidate pages a client has already consumed, so a client that persists query results needs a recovery strategy built on the block references in the response; see Reorg detection.

Because the API supports joins and field projection, the worst-case work for a single request depends on the requested relations and fields as well as on the block range. Implementations should validate relations and fields strictly and bound that worst case.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
