# Tool Outcome Attestation (TOA)

**Open schema + verify libraries** for MCP *tool delivery* evidence (`toa/0.1`).

Apache-2.0 · [Carmel Labs](https://carmel.so) / [AgentStatus](https://agentstatus.dev)

---

## Why this exists

MCP made it easy to *call* tools. It did not make it easy to *prove the call did the job*.

Today most stacks treat success as:

- HTTP `200`
- JSON-RPC without an `error` field
- a body that contains `"success": true`

Those are necessary and nowhere near sufficient. A tool can return empty prose, the wrong shape, soft-error text wrapped as content, or a catalog that drifted from the OpenAPI it was generated from. Host/model evals (right tool? right args?) answer a different question. **Server delivery** is its own axis, and the industry has no shared artifact for it.

TOA is that artifact: a small, **signed** JSON document that records graded layers from a real probe (reach → invoke → functional → shape → …) so CI, gateways, and registries can gate on evidence instead of vibes.

## What this repo is

| Open here | Stays on AgentStatus (product) |
|---|---|
| `toa/0.1` schema + SPEC | Continuous production monitoring |
| Offline verify (Python + JS) | Grading / outcome oracles |
| AgentStatus **public** keys | Emit API + private signing key |
| CI usage examples | Dashboards, alerts, MCP Index |

You can verify anyone’s TOA offline. Emitting AgentStatus-signed attestations requires the product API (or another emitter that signs with its own key).

## What this is not

- Not a new wire protocol (not a second MCP / A2A)
- Not “the server promises it’s healthy” (self-attestations are the problem)
- Not a host/model eval format (those grade the agent; TOA grades the tool reply)
- Not a substitute for live monitoring

## The document (mental model)

```text
Emitter (e.g. AgentStatus) probed tool T at time Z
  → graded layers (pass | fail | warn | n/a)
  → signed the claim with Ed25519
  → you store / attach the JSON

CI or gateway later:
  → verify signature against the emitter’s public key
  → optionally require layers.functional == pass
```

A valid signature means: **this emitter asserted these grades.** It does not mean the MCP server is honest. Pin `emitter.name` and the public key to whoever you trust.

### Layers

| Layer | Question |
|---|---|
| `reach` | Did we reach the server? |
| `invoke` | Did `tools/call` return a protocol-level answer? |
| `functional` | Did the reply look like real delivery (not empty / soft-error junk)? |
| `shape` | Did the body match advertised `outputSchema`? |
| `openapi_fidelity` | Did MCP reply match OpenAPI (often `n/a` for native MCP)? |
| `compositional` | Did multi-step / handle-threading hold when exercised? |

Full field list and signing rules: [`SPEC.md`](./SPEC.md) · schema: [`schema/toa-0.1.schema.json`](./schema/toa-0.1.schema.json)

---

## How to use it

### 1. Get a signed attestation

**AgentStatus customer (emit):**

```http
GET https://api.rora.carmel.so/api/rora/runs/{decision_id}/toa?agent_id={uuid}
Authorization: Bearer <jwt>
```

Optional single tool:

```http
GET …/runs/{decision_id}/toa/{toolName}?agent_id={uuid}
```

Save `attestations[]` (or one document) as `toa.json` in CI artifacts or the PR.

**Other emitters:** implement the same JSON shape, sign with your Ed25519 key, publish your public key. Verifiers must pin *your* key, not AgentStatus’s.

### 2. Verify offline (CI)

**Python**

```bash
cd python && pip install -e .
toa-verify path/to/toa.json \
  --require-emitter agentstatus \
  --require-layer functional=pass
```

**Node 18+**

```bash
cd javascript
node src/cli.js path/to/toa.json \
  --require-emitter agentstatus \
  --require-layer functional=pass
```

Exit `0` only if the signature is valid **and** every `--require-layer` matches. That is the PR gate.

Public key used by default: [`keys/agentstatus-v1.json`](./keys/agentstatus-v1.json).

### 3. Verify via AgentStatus HTTP (no vendored key)

```bash
curl -sS -X POST https://api.rora.carmel.so/api/rora/public/toa/verify \
  -H 'content-type: application/json' \
  -d '{"document": { … full TOA … }}'
```

Returns `{ "valid": true|false, "reason": "…", "layers": {…}, … }`.  
`valid: true` means the signature checks out. **You** still decide whether `layers.functional` is good enough to ship.

### 4. Wire into GitHub Actions

See [`examples/github-action/`](./examples/github-action/) for a starter workflow. Pattern:

1. Earlier job produces or downloads `toa.json`
2. Install `toa-verify`
3. Fail the workflow on nonzero exit

### Try the fixtures in this repo

```bash
# Should pass
toa-verify examples/signed-example.json \
  --require-emitter agentstatus \
  --require-layer functional=pass

# Unsigned → fails
toa-verify examples/unsigned-example.json
```

---

## Who should care

| Audience | Why |
|---|---|
| **MCP server authors** | Gate releases on delivery grades, not “Inspector connected” |
| **Platform / gateway teams** | Require a recent valid TOA before listing or promoting a wrapper |
| **Agent builders** | Separate “model picked the wrong tool” from “tool returned garbage” |
| **Security / procurement** | Portable, signed evidence you can attach to a review pack |

## Trust and threat model (short)

| Claim | True? |
|---|---|
| Bytes were signed by AgentStatus key `v1` | Yes, if verify passes against [`keys/agentstatus-v1.json`](./keys/agentstatus-v1.json) |
| Grades reflect a probe AgentStatus ran | Yes (for AgentStatus-emitted docs) |
| The MCP server cannot lie inside the signature | It never signs; only the emitter does |
| Tampering with `layers` after emit | Detected (`invalid_signature`) |

---

## Layout

| Path | Purpose |
|---|---|
| [`SPEC.md`](./SPEC.md) | Normative field + signing rules |
| [`schema/toa-0.1.schema.json`](./schema/toa-0.1.schema.json) | JSON Schema |
| [`keys/`](./keys/) | Emitter public keys (never private keys) |
| [`python/`](./python/) | `toa-verify` reference implementation |
| [`javascript/`](./javascript/) | Node verify + CLI |
| [`examples/`](./examples/) | Signed/unsigned samples + CI notes |

## Related

- Product docs (emit API): AgentStatus / Rora `toa/0.1` guide in the dashboard backend
- Monitoring product: [agentstatus.dev](https://agentstatus.dev)

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE).

Copyright 2026 Carmel Labs, Inc.
