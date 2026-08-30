# Tool Outcome Attestation (toa/0.1)

**Not a wire protocol.** A portable JSON evidence format that says:

> An emitter graded an MCP tool call into delivery layers, at a point in time, and signed that claim.

AgentStatus continuous monitoring and emit APIs remain proprietary. This repository is the **open schema + offline verify** surface.

## Signed claim fields

These fields are covered by the Ed25519 signature (canonical JSON: UTF-8, sorted keys, separators `,` `:`):

`spec`, `toa_id`, `tool`, `run`, `observed_at`, `layers`, `outcome_grade`, `business_outcome_ok`, `reasons`, `emitter`

Envelope (not signed): `signature`, `payload_hash`, `public_key_id`

## Layers

| Layer | Meaning |
|---|---|
| `reach` | Transport / reachability |
| `invoke` | `tools/call` returned a protocol-level answer |
| `functional` | Delivery grade (operator / schema / substance / …) |
| `shape` | Reply matched advertised `outputSchema` when present |
| `openapi_fidelity` | MCP reply vs OpenAPI (often `n/a` for native MCP) |
| `compositional` | Multi-step / handle-threading when exercised |

Values: `pass` | `fail` | `warn` (shape / openapi only) | `n/a`

## Emitters

`emitter.name` identifies who graded. AgentStatus uses `agentstatus` and key id `v1` ([`keys/agentstatus-v1.json`](./keys/agentstatus-v1.json)).

Other emitters may use this schema with their own keys. Verifiers should pin `require_emitter` / public key to the party they trust.

## How AgentStatus emits today

```http
GET https://api.rora.carmel.so/api/rora/runs/{decision_id}/toa?agent_id={uuid}
Authorization: Bearer <jwt>
```

```http
POST https://api.rora.carmel.so/api/rora/public/toa/verify
{ "document": { … } }
```

## Trust model

A valid signature proves **the named emitter asserted these grades**. It does not prove the MCP server is honest, and it does not replace MCP itself.
