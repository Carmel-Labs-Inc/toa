# SEP-0000: Tool Outcome Attestation Extension

- **Status**: Draft
- **Type**: Extensions Track
- **Created**: 2026-09-06
- **Author(s)**: Abdulrasaq Amolegbe / Carmel Labs (@dulrajnr)
- **Sponsor**: None (seeking sponsor)
- **Extension Identifier**: `dev.agentstatus/toa`
- **Reference implementation**: https://github.com/Carmel-Labs-Inc/toa
- **PR**: (assigned on open)

## Abstract

MCP defines how clients invoke tools. It does not define a shared, verifiable language for whether a tool delivery outcome was actually satisfactory. Implementations today treat JSON-RPC success, HTTP 200, or self-declared server health as proxies for outcome. Those proxies fail closed too late and fail open too often.

This SEP proposes an optional MCP extension, Tool Outcome Attestation (TOA), that negotiates whether `tools/call` results carry a binding to a portable signed `toa/0.1` evidence document, and whether clients may require such a binding under stated trust constraints. Trust is pinned to emitter identity and role (`third_party` | `observer` | `server`), not to "signature present." Verify is offline and does not require an AgentStatus (or any vendor) account.

The incubating extension id is `dev.agentstatus/toa` (SEP-2133 reverse-DNS for `agentstatus.dev`). Official `io.modelcontextprotocol/*` naming is out of scope for this SEP and would require a later acceptance/migration SEP.

## Motivation

1. **Protocol success ≠ delivery success.** A `tools/call` can return empty prose, soft-error text in content, schema-invalid payloads, or broken multi-step handles while still looking like a successful RPC.
2. **Self-attestation is weak.** A server signing "I am fine" recreates the problem outcome attestation exists to escape.
3. **No negotiation surface.** Gateways, hosts, and CI systems lack a capability flag that means "attested outcomes required," so policy stays proprietary and non-interoperable.
4. **Evidence exists off to the side.** `toa/0.1` already defines a signed portable document and offline verify libraries. Without an MCP extension, it cannot participate in capability negotiation or extension conformance.

### Relation to SEP-2809 (ATSA)

Complementary, not competing:

| | ATSA (SEP-2809) | TOA (this SEP) |
|---|---|---|
| When | Before dispatch | On / after tool result |
| Object | Server identity / clearance | Tool call delivery outcome |
| Trust question | Is this server admitted? | Did this call deliver, per a pinned emitter? |

Both can coexist: admit with ATSA, require TOA for high-assurance promote/CI/clients.

### Why an extension (not core)

Outcome attestation is modular and optional. Many clients will never require it. Per SEP-2133, that belongs in an extension: opt-in, composable, independently versioned, with dedicated conformance under `--suite extensions`.

### Why not docs-only CI advice

Documenting `toa-verify` after protocol conformance (as in closed `modelcontextprotocol/conformance#479`) does not create interoperable behavior. Maintainers correctly asked for an extension with tests. This SEP is that submission.

## Specification

The following sections are normative for `dev.agentstatus/toa`. Key words follow RFC 2119 / RFC 8174.

## 1. Overview

The Tool Outcome Attestation (TOA) extension enables MCP clients and servers to negotiate whether `tools/call` results carry a **binding** to a `toa/0.1` attestation document, and whether clients may **require** such a binding under stated trust constraints.

The extension does not replace MCP protocol success semantics. It adds an optional, fail-closed path for parties that demand attested delivery outcomes.

---

## 2. Extension identifier

Implementations of this draft MUST use the extension identifier:

```text
dev.agentstatus/toa
```

Per [SEP-2133](./2133-extensions.md), extension identifiers use `{vendor-prefix}/{extension-name}` where the vendor prefix SHOULD be a **reversed domain name** the author owns or controls. Owning `agentstatus.dev` yields prefix `dev.agentstatus`, hence `dev.agentstatus/toa`.

The hostname-shaped string `agentstatus.dev/toa` is **not** a valid extension identifier and MUST NOT be used on the wire or in capability maps. Product documentation and marketing URLs MAY still use `https://agentstatus.dev/toa`; that URL is not an extension id.

Official MCP adoption, if any, requires a separate SEP assigning an `io.modelcontextprotocol/*` identifier. Until that SEP is accepted, implementations MUST NOT claim the `io.modelcontextprotocol` prefix for this extension.

---

## 3. Dependency on `toa/0.1`

A conforming implementation MUST treat `toa/0.1` (https://github.com/Carmel-Labs-Inc/toa/blob/main/SPEC.md) as the attestation document format, including:

- Signed claim field set and canonical JSON signing input
- Ed25519 signature verification
- Layer vocabulary (`reach`, `invoke`, `functional`, `shape`, `openapi_fidelity`, `compositional`)

This extension MUST NOT invent a parallel grading vocabulary on the wire.

---

## 4. Emitter roles

Every AttestationBinding MUST declare an `emitter_role`:

| Role | Meaning |
|---|---|
| `third_party` | Emitter is not the MCP server under test and not the calling client runtime; independently observed/graded |
| `observer` | Emitter is an on-path observer (e.g. host gateway, local proxy) that witnessed the call |
| `server` | Emitter is the MCP server (or operator) that handled the call |

Security-sensitive clients and gateways SHOULD default `acceptedEmitterRoles` to `["third_party","observer"]` and SHOULD require an explicit choice to accept `server`.

A valid signature MUST be interpreted only as: the named emitter asserted the grades. It MUST NOT be interpreted as proof that the MCP server is honest.

---

## 5. Capability objects

### 5.1 Client settings

When a client advertises `dev.agentstatus/toa`, the capability value MUST be a JSON object with:

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `require` | boolean | no | `false` | If `true`, fail closed without a binding that validates under these settings |
| `acceptedEmitterRoles` | array of role strings | no | `["third_party","observer"]` | Roles accepted for validation |
| `requireEmitter` | string or null | no | `null` | If set, `toa.emitter.name` MUST equal this value |
| `maxAgeSeconds` | number or null | no | `604800` | If set, `observed_at` MUST be within this many seconds of validation time |
| `minLayers` | object | no | see below | Minimum layer outcomes required |

Default `minLayers` when `require` is `true`:

```json
{
  "reach": "pass",
  "invoke": "pass",
  "functional": "pass"
}
```

Layer comparison rules:

- Required value `pass` accepts only `pass`
- Required value `warn` accepts `pass` or `warn`
- `n/a` NEVER satisfies a required `pass` or `warn`
- Layers omitted from `minLayers` are not constrained by this extension

### 5.2 Server settings

When a server advertises `dev.agentstatus/toa`, the capability value MUST be a JSON object with:

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `supportedEmitterRoles` | array of role strings | no | `["third_party","observer","server"]` | Roles this server can attach |
| `attach` | string enum | no | `on_require` | `never` \| `on_require` \| `always` |

Semantics:

- `never` — server advertises understanding/verify assistance only; MUST NOT be relied on to attach
- `on_require` — if the client capability has `require: true`, the server MUST attach a binding on successful `tools/call` results for which it can supply one; if it cannot, it MUST fail closed (see Errors)
- `always` — server MUST attach a binding on successful `tools/call` results when it can; if it cannot for a given call, it MUST fail closed or MUST NOT advertise `always`

---

## 6. Advertising

**Primary target protocol revision:** `2026-07-28` (SEP-2575 stateless model; same negotiation channel as the Tasks extension / SEP-2663).

Under `2026-07-28`, there is no `initialize` handshake. Capabilities MUST NOT be inferred from prior requests. Servers advertise via `server/discover`; clients advertise per request in `_meta`.

### 6.1 Server

A server that implements this extension MUST advertise it in the `capabilities.extensions` object returned by `server/discover`:

```json
{
  "capabilities": {
    "extensions": {
      "dev.agentstatus/toa": {
        "supportedEmitterRoles": ["third_party", "observer"],
        "attach": "on_require"
      }
    }
  }
}
```

### 6.2 Client

A client that implements this extension MUST advertise it on each request where TOA behavior is desired, under per-request client capabilities:

```json
{
  "params": {
    "_meta": {
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "dev.agentstatus/toa": {
            "require": true,
            "acceptedEmitterRoles": ["third_party", "observer"]
          }
        }
      }
    }
  }
}
```

Settings MUST follow §5.1. Servers MUST read TOA client settings only from the current request’s `io.modelcontextprotocol/clientCapabilities` and MUST NOT rely on session-level state.

**Non-normative:** Hosts still speaking protocol revision `2025-11-25` MAY map the same settings objects onto that revision’s `initialize` capability objects for prototyping. Conformance for this draft is defined against `2026-07-28`.

---

## 7. AttestationBinding

If present, the binding MUST appear on the `tools/call` **result**:

```text
result._meta["dev.agentstatus/toa"]
```

### 7.1 Common fields

| Field | Required | Description |
|---|---|---|
| `mode` | yes | `embedded` or `reference` |
| `emitter_role` | yes | `third_party` \| `observer` \| `server` |
| `spec` | yes | MUST be `toa/0.1` for this draft |

### 7.2 `embedded` mode

MUST include `document` — a complete `toa/0.1` object including signature fields required for offline verify.

### 7.3 `reference` mode

MUST include:

| Field | Description |
|---|---|
| `uri` | Locator for the document; scheme MUST be on the §7.4 allowlist |
| `payload_hash` | MUST match `toa.payload_hash` of the resolved document (`sha256:…`) |
| `emitter` | MUST match `document.emitter` after resolve |

Validators that fetch `uri` MUST fail if the document hash mismatches, signature fails, or fetch policy rejects the URI. Validators MAY be configured with a pre-supplied document store keyed by `payload_hash` and MUST still enforce hash and signature checks. Content addressing for v1 is the mandatory `payload_hash`, not a separate URI scheme.

### 7.4 Reference URI scheme allowlist (v1)

For `mode: "reference"`, `uri` MUST use one of:

| Scheme | Normative use |
|---|---|
| `https:` | Production and online fetch. Validators that perform network fetch MUST apply SSRF controls and/or an absolute URI allowlist. |
| `fixture:` | Conformance and local tests only. Form: `fixture:<name>`, resolved from an implementation-defined test fixture store. MUST NOT be accepted as a production trust source unless the implementation is explicitly in test mode. |

Implementations MUST reject reference bindings whose `uri` uses any other scheme (including `http:`, `file:`, `ipfs:`, and invented `toa+…` schemes) unless a later revision of this extension expands the allowlist.

---

## 8. Validation algorithm

When validating a binding against client settings, implementations MUST:

1. Parse `AttestationBinding` and resolve to a `toa/0.1` document (embed or fetch/store).
2. Verify `spec === "toa/0.1"`.
3. Verify Ed25519 signature per `toa/0.1` SPEC (canonical JSON over signed fields).
4. Verify `emitter_role` ∈ `acceptedEmitterRoles`.
5. If `requireEmitter` is set, verify `document.emitter.name === requireEmitter`.
6. If `maxAgeSeconds` is set, verify `observed_at` age ≤ `maxAgeSeconds`.
7. For each entry in `minLayers`, verify layer outcome satisfies §5.1 comparison rules.
8. If `mode === reference`, verify `payload_hash` equals `document.payload_hash`.

Any failed step MUST treat the binding as invalid.

---

## 9. `tools/call` behavior

### 9.1 No negotiation

If the client does not advertise this extension, servers MUST NOT require TOA behavior from that client. Servers MAY still attach bindings; clients MAY ignore unknown `_meta` keys per MCP `_meta` rules.

### 9.2 Client `require: false`

Bindings are optional. Invalid bindings SHOULD be ignored or surfaced as warnings by the client; they MUST NOT convert an otherwise successful core call into a protocol failure unless the client application policy says otherwise.

### 9.3 Client `require: true`

After a successful core `tools/call` result is received (or produced):

- If no binding is present, the client MUST fail closed.
- If a binding is present but validation (§8) fails, the client MUST fail closed.
- Servers advertising `attach: on_require` or `always` MUST attempt to attach a valid binding; if they cannot, they MUST return the error in §10 instead of a successful result without a binding.

### 9.4 Correlation

The attestation’s `tool.name` MUST equal the invoked tool name. The attestation SHOULD include identifiers sufficient to correlate the call (implementation-defined within `toa/0.1` `run` / reasons). Clients MAY reject bindings that clearly refer to a different tool.

---

## 10. Errors

### 10.1 Taxonomy alignment

MCP protocol revision `2026-07-28` defines JSON-RPC error codes as follows ([basic](https://modelcontextprotocol.io/specification/2026-07-28/basic)):

- Standard JSON-RPC: `-32700`, `-32600`..`-32603`
- MCP-reserved: `-32020`..`-32099` (specification-defined only; implementations MUST NOT invent codes here)
- Named MCP codes today include `-32021` `MissingRequiredClientCapability` (server cannot proceed because the client omitted a required capability in per-request `_meta`)

`MissingRequiredClientCapability` MUST NOT be used for TOA `require` failures: polarity is wrong (client demanding attested outcomes from the server, not server demanding undeclared client capabilities).

New codes for purposes not defined by the MCP specification SHOULD be allocated **outside** the JSON-RPC reserved range `-32768`..`-32000`. Therefore this extension MUST NOT use codes in `-32020`..`-32099` (including the withdrawn provisional `-32071`).

### 10.2 `ToaAttestationFailure` (normative for this extension)

When a server must fail closed under §9.3 / §5.2 (`attach: on_require` or `always` and no attachable valid binding), it MUST return a JSON-RPC error:

| Field | Value |
|---|---|
| **code** | `-38100` |
| **name** | `ToaAttestationFailure` |
| **message** | `TOA attestation required` (no binding) or `TOA attestation invalid` (present but fails §8) |
| **data** | object; see below |

`data` MUST include:

- `extensionId`: `"dev.agentstatus/toa"`
- `reason`: one of `missing_binding`, `invalid_signature`, `emitter_role`, `emitter_name`, `expired`, `min_layers`, `hash_mismatch`, `spec_mismatch`, `uri_scheme`, `fetch_rejected`

Clients that fail closed locally after receiving a successful core result with missing/invalid binding under `require: true` MUST treat the call as failed. If they surface that failure in a JSON-RPC-shaped structure, they SHOULD use the same code, name, and `data` shape; that local error MUST NOT be presented as a peer JSON-RPC response.

### 10.3 Migration path

If a future MCP SEP allocates a core or official-extension error code for “required extension constraint unmet,” a later revision of this extension (or an official `io.modelcontextprotocol/toa` SEP) MAY dual-accept that code alongside `-38100` for one protocol revision, then drop `-38100` only under a new extension identifier per SEP-2133 breaking-change rules. Until such a SEP exists, `-38100` / `ToaAttestationFailure` is normative for `dev.agentstatus/toa`.

---

## 11. Privacy

Implementations SHOULD prefer `reference` mode when documents would enlarge results or risk sensitive context. Attestations MUST NOT require raw prompts or raw tool arguments/results to validate under the default `toa/0.1` profile.

---

## 12. Conformance

A claim of conformance to this draft MUST pass the scenarios published with the reference implementation at https://github.com/Carmel-Labs-Inc/toa/blob/main/mcp-extension/conformance/SCENARIOS.md (T1–T10), or equivalent tests once landed under `modelcontextprotocol/conformance` `--suite extensions`.


### Evidence format summary (`toa/0.1`)

Normative schema and signing rules live in the reference repository (`SPEC.md` + JSON Schema). Summary:

- Signed claim fields (canonical JSON, sorted keys, separators `,` `:`): `spec`, `toa_id`, `tool`, `run`, `observed_at`, `layers`, `outcome_grade`, `business_outcome_ok`, `reasons`, `emitter`
- Envelope (not signed): `signature`, `payload_hash`, `public_key_id`
- Layers: `reach`, `invoke`, `functional`, `shape`, `openapi_fidelity`, `compositional` with values `pass` | `fail` | `warn` (shape/openapi) | `n/a`
- Signature: Ed25519; `payload_hash` is `sha256:` of the canonical signed claim bytes

## Rationale

- **Separate evidence document from wire negotiation** so offline CI/gateways can verify without embedding MCP session state, while hosts that want negotiation get a real capability.
- **Role pinning** prevents "valid signature" from being confused with "trusted outcome." Default accepted roles exclude `server`.
- **Vendor-prefixed id while incubating** follows SEP-2133; claiming `io.modelcontextprotocol/toa` unilaterally would be incorrect.
- **Error code outside MCP-reserved range** avoids colliding with specification-owned `-32020..-32099`; polarity of `MissingRequiredClientCapability` is wrong for client-require failures.
- **Primary target `2026-07-28`** matches Tasks / SEP-2575 negotiation channels (`server/discover` + per-request clientCapabilities).

Alternatives considered and rejected for v1:

- Docs-only post-conformance verify (no negotiation; already closed)
- Core protocol change (too heavy; optional feature)
- Server-only self-attestation as trust root (defeats the threat model)
- Putting grades into `isError` (collapses layered delivery evidence into a boolean)

## Backward Compatibility

No backward-incompatible core protocol changes. Extension is disabled unless advertised. Non-supporting peers interoperate on core MCP. Existing `toa/0.1` documents remain valid offline without this extension.

## Security Implications

- Emitter pinning (`requireEmitter` + public key) is mandatory for high-assurance profiles.
- Treating `server` role like `third_party` is a vulnerability; conformance must test rejection.
- Stale evidence: `maxAgeSeconds` bounds replay of old passes.
- Reference fetch SSRF: `https:` fetches require allowlists/SSRF controls; hash mismatch must fail.
- Key compromise: emitters rotate via `key_id`; verifiers pin keys.
- Default `toa/0.1` profile must not require raw prompts or raw tool args/results to validate.

## Reference implementation

https://github.com/Carmel-Labs-Inc/toa

Includes:

- `toa/0.1` schema + Python/JS offline verify
- Wire binding schema + `toa_ext` validate/attach
- MCP Python SDK `ToaAttachExtension` (v2.1+, protocol `2026-07-28`)
- Conformance scenarios T1–T10 + official SDK E2E (in-process and stdio subprocess): advertise, attach-on-require, no-attach without require, fail-closed, crypto edge cases

## Interest group

Security Interest Group (auditability / tamper-evident records of what a tool call did). Tracked next to ATSA without conflating admission and outcome.

## Prior art / related

- SEP-2133 Extensions
- SEP-2663 Tasks Extension (negotiation / conformance quality bar)
- SEP-2809 Attested Tool-Server Admission (complementary admission layer)
- Closed docs-only PR: modelcontextprotocol/conformance#479
