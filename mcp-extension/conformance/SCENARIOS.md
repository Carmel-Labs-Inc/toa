# TOA Extension — Conformance Scenarios

**Quality bar:** match Tasks extension scenarios in `modelcontextprotocol/conformance` (capability negotiation, gating, degradation) — not docs-only checks.

**Extension ID:** `dev.agentstatus/toa`  
**Spec:** [`../specification/draft/toa-extension.md`](../specification/draft/toa-extension.md)

These scenarios are the contract for a future `--suite extensions` contribution. Implement against a reference client/server pair before opening any MCP org PR.

---

## Fixture requirements

### Tools

| Tool | Behavior |
|---|---|
| `echo` | Sync tool; returns `{ "text": <input> }` |
| `soft_fail` | Returns RPC success with empty/soft-error style content that a real grader would mark `functional=fail` (used only when testing emitter honesty — not required for negotiation-only scenarios) |

### Keys / documents

Paths under [`fixtures/`](./fixtures/):

| Artifact | Path |
|---|---|
| Public key | `fixtures/keys/toa-conformance-test-v1.json` |
| Private key (TEST ONLY) | `fixtures/keys/toa-conformance-test-v1.private.json` |
| Golden docs | `fixtures/pass_functional.json`, `fail_functional.json`, `expired.json`, `wrong_tool.json`, `server_role.json`, `bad_signature.json` |

- Emitter: `toa-conformance` / `key_id: test-v1`
- Reference-mode URI scheme for local store: `fixture:<stem>` (e.g. `fixture:pass_functional`)
- See [`fixtures/README.md`](./fixtures/README.md)

---

## Scenario list

### T1 — `toa-capability-advertisement`

**Intent:** Server that claims the extension advertises the correct id and settings shape.

**Checks:**

1. Server capabilities include `extensions["dev.agentstatus/toa"]`
2. Settings object parses; unknown fields ignored; required enums valid
3. Server MUST NOT advertise under a wrong key (e.g. `capabilities.toa`)

**Pass criteria:** all checks PASS.

---

### T2 — `toa-attach-on-require`

**Intent:** `attach: on_require` attaches a binding when client `require: true`.

**Setup:**

- Client advertises extension with `require: true`, `acceptedEmitterRoles: ["third_party"]`
- Server advertises `attach: on_require`, can emit `third_party` test attestations for `echo`

**Checks:**

1. `tools/call echo` result includes `_meta["dev.agentstatus/toa"]`
2. Binding validates under client settings (signature, role, minLayers defaults)
3. `tool.name` matches `echo`

**Pass criteria:** binding present and valid.

---

### T3 — `toa-require-missing-fails-closed`

**Intent:** Client `require: true` without binding is a failure.

**Setup:**

- Client `require: true`
- Server either does not advertise TOA, or advertises `attach: never`, and returns bare success for `echo`

**Checks:**

1. Client-side conformance harness reports fail-closed (`missing_binding`)
2. Core RPC may have succeeded; TOA layer MUST still fail the scenario

**Pass criteria:** scenario FAIL if client accepts the call as TOA-satisfied; PASS if fail-closed observed.

---

### T4 — `toa-role-pinning-rejects-server`

**Intent:** `server` role is not silently trusted.

**Setup:**

- Client `require: true`, `acceptedEmitterRoles: ["third_party"]`
- Server attaches a cryptographically valid attestation with `emitter_role: "server"`

**Checks:**

1. Validation fails with `emitter_role`
2. Call MUST NOT be treated as TOA-satisfied

**Pass criteria:** reject despite valid signature.

---

### T5 — `toa-signature-invalid`

**Intent:** Tampered document fails.

**Setup:** Valid structure, flipped signature byte (or wrong key).

**Checks:** `invalid_signature` fail-closed.

---

### T6 — `toa-min-layers-functional`

**Intent:** `minLayers.functional=pass` rejects `functional=fail` golden.

**Checks:** `min_layers` reason; fail-closed.

---

### T7 — `toa-max-age`

**Intent:** Expired `observed_at` rejected when `maxAgeSeconds` set.

**Checks:** `expired` reason.

---

### T8 — `toa-reference-hash-mismatch`

**Intent:** Reference mode with wrong `payload_hash` fails.

**Checks:** `hash_mismatch`.

---

### T9 — `toa-graceful-degradation`

**Intent:** No client advertisement → core MCP succeeds; TOA not required.

**Setup:** Client without extension; server may or may not attach.

**Checks:**

1. `echo` succeeds as core tool call
2. No TOA error codes introduced

---

### T10 — `toa-require-emitter-name`

**Intent:** `requireEmitter: "toa-conformance"` rejects other `emitter.name` even if role ok and sig valid under a different key accepted by a misconfigured store.

**Checks:** `emitter_name` (harness pins keys carefully).

---

## Implementation order

1. Golden documents + verify helpers (reuse `toa` python/js verify)
2. T1, T9 (advertisement + degradation)
3. T2, T3 (attach + require)
4. T4–T8, T10 (trust edge cases)
5. Only then approach MCP conformance harness integration

## Non-goals for v1 scenarios

- Proving AgentStatus production grading quality
- Fabric Live multi-host capture
- Hard-1 model consideration metrics
- Official `io.modelcontextprotocol/toa` naming

---

## Tracking

Harness: [`harness/`](./harness/) — in-process fake MCP + scenario runner.  
Validate: prefers `toa_ext` (`toa/python/toa_ext`); stub fallback if absent.  
Fixtures: [`fixtures/`](./fixtures/).

| Scenario | Status |
|---|---|
| T1 advertisement | harness PASS |
| T2 attach on require | harness PASS (uses `pass_functional` + key) |
| T3 require missing | harness PASS |
| T4 role pinning | harness PASS (was library unit; now end-to-end) |
| T5 bad signature | harness PASS |
| T6 min layers | harness PASS |
| T7 max age | harness PASS |
| T8 hash mismatch | harness PASS |
| T9 degradation | harness PASS |
| T10 require emitter | harness PASS (inverted `requireEmitter` until `other_emitter` golden) |
| T11 negotiation record | spec added 2026-09-07 — implement next |
| T12 signed negative disposition | spec added 2026-09-07 — implement next |
| T13 absence vs never-advertised | spec added 2026-09-07 — implement next |

---

## T11 — `toa-negotiation-record`

**Intent:** Client/gateway persists NegotiationRecord at discover so offline absence is interpretable.

**Checks:**

1. After discover where server advertises TOA, a `toa-negotiation/0.1` record exists with `server_advertised_toa: true` and settings copy
2. After discover where server does not advertise TOA, record has `server_advertised_toa: false`
3. Schema validates against `toa-negotiation-0.1.schema.json`

---

## T12 — `toa-signed-negative-disposition`

**Intent:** Failure paths emit signed evidence, not silence.

**Setup:** Server `attach: on_require`; client `require: true`; tool returns `isError` / graded fail.

**Checks:**

1. Binding present on the negative path
2. Document verifies; `disposition` is `failed` or `refused` or `unavailable` (or layers fail required minLayers)
3. Must not be an attestation gap

---

## T13 — `toa-absence-vs-never-advertised`

**Intent:** Offline verifier distinguishes “never advertised TOA” from “advertised but missing attestation.”

**Checks:**

1. With NegotiationRecord `server_advertised_toa: false` and no docs → class `outside_toa`
2. With NegotiationRecord `server_advertised_toa: true` and no doc for a required call → class `attestation_gap`
3. Those classes MUST NOT be equal
