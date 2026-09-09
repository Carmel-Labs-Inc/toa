# SEP-0000: Tool Outcome Attestation Extension

- **Status**: Draft
- **Type**: Extensions Track
- **Created**: 2026-09-06
- **Author(s)**: Abdulrasaq Amolegbe / Carmel Labs (@dulrajnr)
- **Sponsor**: None (seeking sponsor)
- **Extension Identifier**: `dev.agentstatus/toa`
- **Reference implementation**: https://github.com/Carmel-Labs-Inc/toa
- **Tracking issue**: https://github.com/modelcontextprotocol/modelcontextprotocol/issues/3350
- **PR**: (blocked for non-collaborators; branch ready)

## Abstract

MCP defines how clients invoke tools. It does not define a shared, verifiable language for whether a tool delivery outcome was actually satisfactory. Implementations today treat JSON-RPC success, HTTP 200, or self-declared server health as proxies for outcome. Those proxies fail closed too late and fail open too often.

This SEP proposes an optional MCP extension, Tool Outcome Attestation (TOA), that negotiates whether `tools/call` results carry a binding to a portable signed `toa/0.1` evidence document, and whether clients may require such a binding under stated trust constraints. Trust is pinned to emitter identity and role (`third_party` | `observer` | `server`), not to "signature present." Verify is offline and does not require an AgentStatus (or any vendor) account.

Absence is addressed explicitly: clients persist NegotiationRecords (`toa-negotiation/0.1`) so "never advertised TOA" is distinct from "advertised but missing attestation," and servers that advertise attach MUST emit signed negative outcomes (`disposition` / failing layers) instead of silence on failure.

The incubating extension id is `dev.agentstatus/toa` (SEP-2133 reverse-DNS for `agentstatus.dev`). Official `io.modelcontextprotocol/*` naming is out of scope for this SEP and would require a later acceptance/migration SEP.

## Motivation

1. **Protocol success ≠ delivery success.** A `tools/call` can return empty prose, soft-error text in content, schema-invalid payloads, or broken multi-step handles while still looking like a successful RPC.
2. **Self-attestation is weak.** A server signing "I am fine" recreates the problem outcome attestation exists to escape.
3. **No negotiation surface.** Gateways, hosts, and CI systems lack a capability flag that means "attested outcomes required," so policy stays proprietary and non-interoperable.
4. **Evidence exists off to the side.** `toa/0.1` already defines a signed portable document and offline verify libraries. Without an MCP extension, it cannot participate in capability negotiation or extension conformance.
5. **Absence must be informative.** A verifier with no attestation must distinguish "server never implemented TOA" from "server advertised TOA and failed/omitted evidence." Otherwise incentives favor going silent on failure.

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
| `requireArgsHash` | boolean | no | `false` | If `true`, fail closed unless the document includes a valid `args_hash` |

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
3. Resolve envelope `alg` (absent means `Ed25519`); if unsupported, fail (`unsupported_algorithm`).
4. Verify signature per `toa/0.1` SPEC for that algorithm (canonical JSON over signed fields).
5. Verify `emitter_role` ∈ `acceptedEmitterRoles`.
6. If `requireEmitter` is set, verify `document.emitter.name === requireEmitter`.
7. If `maxAgeSeconds` is set, verify `observed_at` age ≤ `maxAgeSeconds`.
8. For each entry in `minLayers`, verify layer outcome satisfies §5.1 comparison rules.
9. If `mode === reference`, verify `payload_hash` equals `document.payload_hash`.
10. If `args_hash` is present, verify format (`sha256:` + 64 hex). If `requireArgsHash` is true, `args_hash` MUST be present. If the client supplies an expected args digest for this call, it MUST equal `args_hash`.

Any failed step MUST treat the binding as invalid.

---

## 9. `tools/call` behavior

### 9.1 No negotiation

If the client does not advertise this extension, servers MUST NOT require TOA behavior from that client. Servers MAY still attach bindings; clients MAY ignore unknown `_meta` keys per MCP `_meta` rules.

### 9.2 Client `require: false`

Bindings are optional. Invalid bindings SHOULD be ignored or surfaced as warnings by the client; they MUST NOT convert an otherwise successful core call into a protocol failure unless the client application policy says otherwise.

### 9.3 Client `require: true`

After a `tools/call` completes (successful result, `isError: true` result, or peer error):

- If no binding is present when the server advertised this extension with `attach` in (`on_require`, `always`), the client MUST fail closed and MUST record the miss against the negotiation record (§13).
- If a binding is present but validation (§8) fails, the client MUST fail closed.
- Servers advertising `attach: on_require` or `always` MUST attach a valid binding on **both** positive and negative delivery paths (§14); if they cannot, they MUST return the error in §10 instead of a bare result/error without a binding.

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
- `reason`: one of `missing_binding`, `invalid_signature`, `emitter_role`, `emitter_name`, `expired`, `min_layers`, `hash_mismatch`, `spec_mismatch`, `uri_scheme`, `fetch_rejected`, `args_hash`, `unsupported_algorithm`

Clients that fail closed locally after receiving a successful core result with missing/invalid binding under `require: true` MUST treat the call as failed. If they surface that failure in a JSON-RPC-shaped structure, they SHOULD use the same code, name, and `data` shape; that local error MUST NOT be presented as a peer JSON-RPC response.

### 10.3 Migration path

If a future MCP SEP allocates a core or official-extension error code for “required extension constraint unmet,” a later revision of this extension (or an official `io.modelcontextprotocol/toa` SEP) MAY dual-accept that code alongside `-38100` for one protocol revision, then drop `-38100` only under a new extension identifier per SEP-2133 breaking-change rules. Until such a SEP exists, `-38100` / `ToaAttestationFailure` is normative for `dev.agentstatus/toa`.

---

## 11. Privacy

Implementations SHOULD prefer `reference` mode when documents would enlarge results or risk sensitive context. Attestations MUST NOT require raw prompts or raw tool arguments/results to validate under the default `toa/0.1` profile.

Optional signed `args_hash` MAY bind a digest of arguments without embedding the raw args. Clients that need stronger anti-substitution guarantees SHOULD set `requireArgsHash: true` and recompute the digest locally.

---

## 12. Conformance

A claim of conformance to this draft MUST pass the scenarios at https://github.com/Carmel-Labs-Inc/toa/blob/main/mcp-extension/conformance/SCENARIOS.md (including T11–T13 absence/negative, T14–T15 args_hash, and T16 key-pin scenarios), or equivalent tests once landed under `modelcontextprotocol/conformance` `--suite extensions`.

---

## 13. Absence semantics and negotiation records

### 13.1 Problem

A verifier holding only a bag of `toa/0.1` documents cannot, from silence alone, distinguish:

1. The server never implemented / advertised this extension
2. The server advertised this extension and delivery failed
3. The server advertised this extension and omitted attestation for this call

Without additional structure, offline absence is information-free and incentives run backwards: stopping attestation when things fail is indistinguishable from never supporting TOA.

### 13.2 NegotiationRecord (normative companion)

Clients and gateways that perform offline or post-hoc verification MUST persist a **NegotiationRecord** whenever they complete `server/discover` (or the protocol revision’s equivalent capability advertisement) against a server.

`NegotiationRecord` MUST be a JSON object:

| Field | Required | Meaning |
|---|---|---|
| `spec` | yes | MUST be `toa-negotiation/0.1` |
| `recorded_at` | yes | RFC 3339 time the record was written |
| `protocol_version` | yes | Negotiated MCP protocol version string |
| `server_id` | yes | Stable server identifier used by the client (implementation-defined; SHOULD match `toa.tool.server_id` when later attestations exist) |
| `server_advertised_toa` | yes | boolean — `true` iff `capabilities.extensions["dev.agentstatus/toa"]` was present |
| `server_settings` | no | Copy of the advertised settings object when `server_advertised_toa` is true |
| `client_settings` | no | Client TOA settings used for subsequent calls in this context |
| `discover_request_id` | no | Correlation id for the discover exchange |
| `pinned_public_key_id` | no | Client-pinned `public_key_id` / `emitter.key_id` expected for this server |
| `pinned_key_fingerprint` | no | `sha256:` hex of the raw public key bytes the client trusts |
| `pinned_emitter_name` | no | Optional pin of `emitter.name` |
| `transport` | no | `stdio` \| `http` \| `sse` \| `other` — informational; does not change who signs |

NegotiationRecord is **client-local evidence of advertisement and trust pins**, not a server-signed claim. Key pins are **out-of-band**: the server MUST NOT be treated as authoritative for which public key the client trusts. Implementations MAY additionally obtain an observer-signed copy; that is optional and does not replace the client obligation to record advertisement and pins.

Schema: https://github.com/Carmel-Labs-Inc/toa/blob/main/mcp-extension/schema/toa-negotiation-0.1.schema.json

### 13.3 Interpreting absence offline

Given a NegotiationRecord and a set of attestations for the same `server_id` / time window:

| `server_advertised_toa` | Attestation present for call | Offline conclusion |
|---|---|---|
| `false` | no | Expected: server outside TOA |
| `true` | yes (disposition delivered / layers pass) | Positive evidence |
| `true` | yes (disposition failed/refused/unavailable or failing layers) | **Negative evidence** (§14) |
| `true` | no for a call that required attach | **Attestation gap** — distinct from “never supported TOA”; MUST NOT be collapsed into (1) |
| `true` | yes, but verifier has no trusted key | **`key_unavailable`** — MUST NOT be collapsed into attestation gap |
| `true` | yes, but key/fingerprint does not match pin (or signature fails under the pinned key) | **`untrusted_key`** — MUST NOT be collapsed into attestation gap |

Verifiers MUST treat “attestation gap”, “server never advertised TOA”, `key_unavailable`, and `untrusted_key` as different outcome classes.

---

## 14. Signed negative outcomes

### 14.1 Mandatory attach on failure paths

When a server advertises `attach: on_require` or `attach: always` and the client has advertised this extension (with `require: true` for `on_require`):

- The server MUST attach a binding not only on successful delivery, but also when the tool result has `isError: true`, when delivery is graded as failed by the emitter, or when the server refuses the call under TOA policy.
- Omitting a binding on those paths is non-conformant and MUST be recorded by the client as an attestation gap (§13.3) when negotiation said TOA was advertised.

### 14.2 `disposition` on `toa/0.1` (additive)

Documents MAY include signed field `disposition` (part of the signed claim set when present):

| Value | Meaning |
|---|---|
| `delivered` | Emitter asserts delivery succeeded under its grading policy |
| `failed` | Emitter asserts the call was attempted and delivery failed |
| `refused` | Emitter asserts the call was refused (policy / auth / capability) before meaningful delivery |
| `unavailable` | Emitter asserts the server/tool was unreachable or could not be invoked |

If `disposition` is absent, verifiers MAY infer a coarse signal from layers (`functional=fail` / `reach=fail` etc.) but emitters that advertise this extension SHOULD set `disposition` explicitly on negative paths.

A cryptographically valid attestation with `disposition` in (`failed`, `refused`, `unavailable`) or with failing required layers **is** negative evidence. It MUST NOT be treated as silence.

### 14.3 Incentive alignment

Servers that advertise TOA and then go silent on failure are distinguishable from non-TOA servers **only if** clients persist NegotiationRecords (§13). Spec-conformant servers do not rely on that distinction: they emit signed negative outcomes (§14.1–14.2) instead of silence.

## 15. Trust anchors, revocation, and transport

TOA does **not** define a public-key infrastructure. Offline verify requires the verifier to already hold a trusted public key for the emitter.

### 15.1 Key distribution and pinning

- Clients/gateways configure trust anchors **out of band**.
- At capability exchange, clients SHOULD record the pin they will use for this server on the NegotiationRecord (`pinned_public_key_id`, `pinned_key_fingerprint`, optional `pinned_emitter_name`).
- A signature failure or missing trusted key MUST be classified as `untrusted_key` or `key_unavailable`, not as `attestation_gap`.

### 15.2 Revocation of already-signed evidence

Default policy: **`valid_at_observed_at`**. If the signing key was not revoked at `observed_at`, a cryptographically valid signature remains historically acceptable even if the key is later revoked. Verifiers MAY apply stricter `invalid_if_revoked_now` and MUST name that policy. TOA does not mandate CRL/OCSP or a key server.

### 15.3 Stdio and other transports

Transport does not choose the signer. The **emitter** key signs. For `emitter_role: server`, the key belongs to the process operator even when the client spawned a stdio subprocess. NegotiationRecord `transport: "stdio"` is informational only.

### Evidence format summary (`toa/0.1`)

Normative schema and signing rules live in the reference repository (`SPEC.md` + JSON Schema). Summary:

- Signed claim fields (canonical JSON, sorted keys, separators `,` `:`): `spec`, `toa_id`, `tool`, `run`, `observed_at`, `layers`, `outcome_grade`, `business_outcome_ok`, `reasons`, `emitter`, and when present `disposition`, `args_hash`
- Envelope (not signed): `signature`, `payload_hash`, `public_key_id`, `alg` (absent `alg` means Ed25519)
- Layers: `reach`, `invoke`, `functional`, `shape`, `openapi_fidelity`, `compositional` with values `pass` | `fail` | `warn` (shape/openapi) | `n/a`
- Optional `disposition`: `delivered` | `failed` | `refused` | `unavailable`
- Optional `args_hash`: `sha256:` + hex; when present MUST be checked; requiring it when absent is verifier policy (`requireArgsHash`)
- Signature: algorithm selected by envelope `alg` (default Ed25519); `payload_hash` is `sha256:` of the canonical signed claim bytes
- Only Ed25519 is required to be implemented for `toa/0.1`; unknown algorithms MUST fail closed

## Rationale

- **Separate evidence document from wire negotiation** so offline CI/gateways can verify without embedding MCP session state, while hosts that want negotiation get a real capability.
- **Role pinning** prevents "valid signature" from being confused with "trusted outcome." Default accepted roles exclude `server`.
- **NegotiationRecord + signed negatives** make absence interpretable and remove the incentive to go silent on failure.
- **Vendor-prefixed id while incubating** follows SEP-2133; claiming `io.modelcontextprotocol/toa` unilaterally would be incorrect.
- **Error code outside MCP-reserved range** avoids colliding with specification-owned `-32020..-32099`; polarity of `MissingRequiredClientCapability` is wrong for client-require failures.
- **Primary target `2026-07-28`** matches Tasks / SEP-2575 negotiation channels (`server/discover` + per-request clientCapabilities).

## Backward Compatibility

No backward-incompatible core protocol changes. Extension is disabled unless advertised. Non-supporting peers interoperate on core MCP. Existing `toa/0.1` documents without `disposition`, `args_hash`, or `alg` remain valid; those fields are additive (`alg` defaults to Ed25519 when absent).

## Security Implications

- Emitter pinning (`requireEmitter` + public key) is mandatory for high-assurance profiles.
- Treating `server` role like `third_party` is a vulnerability; conformance must test rejection.
- Stale evidence: `maxAgeSeconds` bounds replay of old passes.
- Reference fetch SSRF: `https:` fetches require allowlists/SSRF controls; hash mismatch must fail.
- Key compromise: emitters rotate via `key_id`; verifiers pin keys.
- Default `toa/0.1` profile must not require raw prompts or raw tool args/results to validate.
- NegotiationRecords are client-local; treat them as integrity-sensitive logs if used for compliance conclusions.

## Reference implementation

https://github.com/Carmel-Labs-Inc/toa

## Interest group

Security Interest Group. Tracking issue: https://github.com/modelcontextprotocol/modelcontextprotocol/issues/3350

## Prior art / related

- SEP-2133 Extensions
- SEP-2663 Tasks Extension
- SEP-2809 Attested Tool-Server Admission
- Closed docs-only PR: modelcontextprotocol/conformance#479
