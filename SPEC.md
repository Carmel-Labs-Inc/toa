# Tool Outcome Attestation (toa/0.1)

**Not a wire protocol.** A portable JSON evidence format that says:

> An emitter graded an MCP tool call into delivery layers, at a point in time, and signed that claim.

AgentStatus continuous monitoring and emit APIs remain proprietary. This repository is the **open schema + offline verify** surface.

## Signed claim fields

These fields are covered by the signature (canonical JSON: UTF-8, sorted keys, separators `,` `:`):

`spec`, `toa_id`, `tool`, `run`, `observed_at`, `layers`, `outcome_grade`, `business_outcome_ok`, `reasons`, `emitter`, and when present `disposition`, `args_hash`

Envelope (not signed): `signature`, `payload_hash`, `public_key_id`, `alg`

### Algorithm (`alg`, envelope)

- Absent `alg` means **Ed25519** (backward compatible with existing `toa/0.1` documents).
- Emitters SHOULD set `alg: "Ed25519"` on new documents.
- Verifiers MUST fail closed on unknown algorithms (`unsupported_algorithm`).
- Only Ed25519 is required to be implemented for `toa/0.1`. Additional suites are a later revision or key-discovery concern, not a break of existing evidence.

### Disposition (optional, signed when present)

| Value | Meaning |
|---|---|
| `delivered` | Delivery succeeded under the emitter’s grading policy |
| `failed` | Call attempted; delivery failed |
| `refused` | Refused before meaningful delivery (policy / auth / capability) |
| `unavailable` | Unreachable / could not invoke |

Emitters implementing MCP extension `dev.agentstatus/toa` SHOULD set `disposition` explicitly on negative paths so offline verifiers do not confuse failure with silence. `disposition=delivered` plus a failing core layer is `inconsistent_claims`, not positive evidence.

### `args_hash` (optional, signed when present)

Commitment to tool arguments: `sha256:` + hex of canonical JSON of the arguments object.

- When present, verifiers MUST validate format and, if they know the call args, MUST check equality.
- When absent, requiring it is a **verifier policy** decision (`require_args_hash` / client `requireArgsHash`), not a format default.
- Raw arguments MUST NOT be required in the document (privacy).

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

Trust anchors are configured **out of band**. Clients SHOULD record pins on the NegotiationRecord (`pinned_public_key_id` / `pinned_key_fingerprint`). Missing key or pin mismatch is `key_unavailable` / `untrusted_key`, not an attestation gap. Revocation policy is per-verifier on the NegotiationRecord (`valid_at_observed_at` for ledger, `invalid_if_revoked_now` for action gates). Absent policy plus a revoke timestamp fails closed. `invalid_if_revoked_now` with no revocation source is `revocation_status_unavailable`, not accept. When a NegotiationRecord is used as audit evidence, an observer-signed copy SHOULD be persisted. See MCP extension draft §13.2 / §15.
