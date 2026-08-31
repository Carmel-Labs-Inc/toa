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
  --require-layer functional=pass \
  --max-age 7d
```

**Node 18+**

```bash
cd javascript
node src/cli.js path/to/toa.json \
  --require-emitter agentstatus \
  --require-layer functional=pass \
  --max-age 7d
```

Exit `0` only if the signature is valid **and** every `--require-layer` matches. That is the PR gate.

Optional freshness: `--max-age 7d` (also `24h`, `90m`, or raw seconds) fails with `stale_attestation` when `observed_at` is too old.

Public key used by default: [`keys/agentstatus-v1.json`](./keys/agentstatus-v1.json) (also packaged inside `toa_verify` so `pip install ...#subdirectory=python` works without a separate key checkout).

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

## Use cases by audience

These are **roles and company classes**, not claims that every named company already uses TOA. Use them to map who verifies, who emits, and who requires the artifact.

### 1. Pre-prod / CI tooling (MCPJam-class)

**Job:** catch MCP regressions before merge.  
**Examples of the class:** MCPJam, custom Jest/Vitest harnesses, GitHub Actions “doctor” jobs.

**How TOA fits:** after doctor / protocol conformance / host evals, add one step that verifies a TOA (or emits one from richer delivery checks) and fails on `layers.functional != pass` or `shape == fail`.  
**Does not replace:** OAuth debugger, client-matrix, LLM evals, JSON-RPC traces.

### 2. Gateways & control planes (Nasiko / Composio-class)

**Job:** decide which MCP servers and tools agents may call in production.  
**Examples of the class:** Nasiko, Composio, Zapier MCP, enterprise internal gateways, API management teams wrapping MCP.

**How TOA fits:** allowlist / promote a connector only when a recent TOA verifies for a trusted emitter. Policy can require `functional=pass` and treat `shape=fail` as block.  
**Does not replace:** auth, budgets, TokenOps, A2A routing.

### 3. Registries & directories (Smithery / Pulse-class)

**Job:** catalog and rank MCP servers for discovery.  
**Examples of the class:** Smithery, Glama, PulseMCP, curated internal catalogs.

**How TOA fits:** show “last attested delivery” next to stars/downloads; demote or flag servers whose latest TOA fails functional/shape.  
**Does not replace:** search, packaging, install UX.

### 4. MCP server authors (ISVs & open-source)

**Job:** ship tools that hosts and gateways will trust.  
**Examples of the class:** DeepWiki/Cognition-style public MCPs, Stripe/Notion/Linear-style product MCPs, FastMCP starters, internal platform teams publishing company tools.

**How TOA fits:** attach a signed TOA to the release or README; run `toa-verify` in CI before tag. Proves delivery grades, not just “Inspector connected.”  
**Does not replace:** unit tests or their own eval suites.

### 5. Agent product teams (builders on Cursor / Claude / ChatGPT)

**Job:** ship agents that depend on third-party MCP tools.  
**Examples of the class:** startups wiring Composio tools, enterprises wiring internal MCP to Claude Desktop / Cursor / custom harnesses.

**How TOA fits:** separate “our model picked the wrong tool” from “the tool returned empty success.” Require TOA on critical connectors in staging.  
**Does not replace:** product evals or tracing (LangSmith-class).

### 6. Security, risk, procurement

**Job:** approve agent stacks that call external tools.  
**Examples of the class:** bank / healthcare AI governance, SOC2 vendors, IT risk reviewing MCP gateways.

**How TOA fits:** portable signed evidence in the diligence pack (“independent observer graded delivery on date X”). Prefer emitters you trust; verify offline.  
**Does not replace:** legal review, penetration tests, or vendor questionnaires.

### 7. Continuous monitoring (AgentStatus)

**Job:** watch MCP servers after ship, from real probes over time.  
**How TOA fits:** AgentStatus **emits** TOA from production runs; open verify lets CI and partners consume the same grades.  
**Does not replace:** dashboards, alerts, MRI / MCP Index, multi-step workflows.

### Suggested CI sandwich (pre-prod + evidence)

```text
MCPJam doctor / protocol conformance
        +
MCPJam (or other) host/model evals     ← “did the agent pick the right tool?”
        +
toa-verify (AgentStatus or local emit) ← “did the tool actually deliver?”
        →
gateway / registry promote
```

Hands-on note (Aug 2026): MCPJam `server doctor` on a live public MCP confirmed connect + tools/list + **input** schema checks. Protocol profile still lists `modern-tool-output-schema-conformant` as **pending / unscored**. That is the delivery/shape gap TOA is built for.

---

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
| [`docs/MCPJAM_CEO_BRIEF.md`](./docs/MCPJAM_CEO_BRIEF.md) | Hands-on complementarity notes (MCPJam) |

## Related

- Product docs (emit API): AgentStatus / Rora `toa/0.1` guide in the dashboard backend
- Monitoring product: [agentstatus.dev](https://agentstatus.dev)

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE).

Copyright 2026 Carmel Labs, Inc.
