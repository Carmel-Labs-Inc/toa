# SEP Draft: Tool Outcome Attestation (TOA) MCP Extension

- **Status:** Draft (incubating outside MCP org)
- **Type:** Standards Track (Extensions Track)
- **Created:** 2026-09-06
- **Author(s):** Carmel Labs / AgentStatus (`@dulrajnr` / Carmel-Labs-Inc)
- **Extension ID (incubating):** `dev.agentstatus/toa`
- **Evidence format:** `toa/0.1` ([Carmel-Labs-Inc/toa](https://github.com/Carmel-Labs-Inc/toa))
- **Sponsor:** none yet (required before MCP org experimental-ext)
- **Related:** Closed docs-only attempt [modelcontextprotocol/conformance#479](https://github.com/modelcontextprotocol/conformance/pull/479) — maintainer guidance: propose an extension with conformance tests

This draft follows [SEP-2133: Extensions](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md) structure and MUST stay aligned with [`THESIS.md`](./THESIS.md).

---

## Abstract

MCP defines how clients invoke tools. It does not define a shared, verifiable language for whether a tool **delivery outcome** was actually satisfactory. Implementations today treat JSON-RPC success, HTTP 200, or self-declared server health as proxies for outcome. Those proxies fail closed too late and fail open too often.

This SEP proposes an **optional MCP extension** that negotiates Tool Outcome Attestation (TOA): clients and servers advertise whether attested outcomes can be required or attached on `tools/call` results, using the portable `toa/0.1` signed evidence document as the attestation payload. Trust is pinned to **emitter identity and role** (third-party / observer / server), not to “signature present.”

---

## Motivation

### Problem

1. **Protocol success ≠ delivery success.** A `tools/call` can return empty prose, soft-error text in content, schema-invalid payloads, or broken multi-step handles while still looking like a successful RPC.
2. **Self-attestation is weak.** A server signing “I am fine” recreates the problem TOA was designed to avoid.
3. **No negotiation surface.** Gateways, hosts, and CI systems lack a capability flag that means “attested outcomes required,” so policy stays proprietary and non-interoperable.
4. **Evidence exists but is off to the side.** `toa/0.1` already defines a signed portable document and offline verify. Without an MCP extension, it cannot participate in capability negotiation or conformance.

### Why an extension (not core)

Outcome attestation is modular and optional. Many clients will never require it. Per SEP-2133, that belongs in an extension: opt-in, composable, independently versioned, with dedicated conformance under `--suite extensions`.

### Why not docs-only CI advice

Documenting `toa-verify` after conformance (as in closed PR #479) does not create interoperable behavior. Maintainers correctly asked for an extension with tests.

---

## Specification

Normative wire behavior lives in [`specification/draft/toa-extension.md`](./specification/draft/toa-extension.md). Summary:

### Extension identifier

Incubating wire id: `dev.agentstatus/toa`

Per SEP-2133, vendor prefixes are **reversed domain names**. Owning `agentstatus.dev` → prefix `dev.agentstatus` → id `dev.agentstatus/toa`. Literal `agentstatus.dev/toa` is **not** a valid extension identifier. Product/docs URL MAY remain `https://agentstatus.dev/toa`.

If later accepted as an official MCP extension, a new SEP MUST assign `io.modelcontextprotocol/toa` (or another `io.modelcontextprotocol/*` id) and define the migration. Do not rename unilaterally.

### Capability negotiation

**Primary target protocol revision: `2026-07-28`** (SEP-2575).

- Clients advertise under per-request `_meta["io.modelcontextprotocol/clientCapabilities"].extensions["dev.agentstatus/toa"]` with settings (`require`, `acceptedEmitterRoles`, `requireEmitter`, `maxAgeSeconds`, `minLayers`).
- Servers advertise under `server/discover` → `capabilities.extensions["dev.agentstatus/toa"]` with settings (`supportedEmitterRoles`, `attach`).
- If the client sets `require: true`, a `tools/call` result without a binding that verifies under those settings MUST fail closed using `ToaAttestationFailure` (`-38100`) as defined in the wire spec.
- If neither side advertises the extension, core `tools/call` behavior MUST be unchanged.
- Do not rely on session/`initialize` advertisement for the primary target revision (handshake removed in `2026-07-28`).

### Wire binding

Successful `tools/call` results MAY include:

```text
result._meta["dev.agentstatus/toa"] = AttestationBinding
```

Binding modes: `embedded` (full `toa/0.1` document) or `reference` (uri + `payload_hash` + emitter metadata). Validation MUST verify the `toa/0.1` signature and apply client constraints (role, emitter, age, min layers).

### Trust model (normative intent)

A valid signature proves: **the named emitter asserted these grades at this time.** It does not prove the MCP server is honest. Conformance and examples MUST demonstrate role pinning. Profiles that accept `server` role MUST document the weaker trust implications.

### Relationship to `toa/0.1`

This extension does not redefine grading layers. It binds MCP sessions to the existing evidence format. Schema evolution of `toa/0.1` is independent; wire breaking changes require a new extension id.

---

## Privacy considerations

Default attestations MUST NOT require raw prompts, raw tool arguments, or raw result bodies. `toa/0.1` already targets grades, identifiers, and hashes. Embedded mode SHOULD avoid enlarging results with sensitive payloads; reference mode is preferred for large or sensitive deployments.

---

## Backwards compatibility

- Extension is disabled unless advertised (SEP-2133 default).
- Non-supporting peers interoperate on core MCP.
- Existing `toa/0.1` documents remain valid offline without this extension.

---

## Security considerations

- **Emitter pinning** is mandatory for high-assurance profiles (`requireEmitter` + public key).
- **Role confusion:** treating `server` like `third_party` is a vulnerability. Spec and conformance MUST test rejection when role is not accepted.
- **Stale evidence:** `maxAgeSeconds` prevents replaying old pass attestations.
- **Reference fetch SSRF:** verifiers that fetch `uri` MUST apply allowlists / SSRF controls; only `https:` and test-only `fixture:` are allowed in v1; hash mismatch MUST fail.
- **Key compromise:** emitters MUST rotate keys via published key ids; verifiers MUST pin `key_id`.

---

## Conformance plan

See [`conformance/SCENARIOS.md`](./conformance/SCENARIOS.md). Minimum scenarios before proposing MCP org experimental status:

1. Capability advertisement shape
2. Attach on require
3. Fail closed when require unmet
4. Role pinning reject `server` when not accepted
5. Signature verify success/fail fixtures
6. Graceful degradation without negotiation
7. Reference hash mismatch fail

Target harness: `modelcontextprotocol/conformance` `--suite extensions` (after incubation), matching Tasks extension quality bar.

---

## Reference implementation requirements (SEP-2133)

Before requesting MCP Core Maintainer review for official status:

1. Spec text (RFC 2119) complete in this tree
2. At least one SDK reference path that can advertise, attach, and verify bindings
3. Automated tests for the scenarios above
4. Associated Interest Group or Working Group under MCP community process (start: Security IG; see Decisions)

Incubation MAY begin on `Carmel-Labs-Inc/toa` prior to MCP org `experimental-ext-*`.

---

## Rationale

### Why not only gateway policy?

Proprietary gateway checks do not create a shared client/server vocabulary. Negotiation makes require/attach portable across hosts and SDKs.

### Why not put grades in core `isError`?

Core protocol success is intentionally narrow. Outcome grading is layered and emitter-relative; forcing it into core would politicize every `tools/call`.

### Why keep AgentStatus out of the trust root?

Protocol adoption dies if verify requires a vendor account. AgentStatus competes as an emitter quality + observation network, not as a chokepoint.

---

## Decisions (closed 2026-09-06)

Full rationale: [`DECISIONS.md`](./DECISIONS.md). Normative wire text: [`specification/draft/toa-extension.md`](./specification/draft/toa-extension.md).

1. **Error when `require` unmet:** JSON-RPC code `-38100`, name `ToaAttestationFailure`, with `data.extensionId` + `data.reason`. Not `-32021` (`MissingRequiredClientCapability`; wrong polarity) and not any code in MCP-reserved `-32020`..`-32099` (withdrawn provisional `-32071`). Migration: dual-accept a future MCP-allocated code only under a later revision / new extension id.
2. **Advertise channel:** Target protocol revision `2026-07-28`. Client: per-request `_meta` `clientCapabilities.extensions`. Server: `server/discover` capabilities. Follows Tasks / SEP-2575; not initialize/session-level for the primary target.
3. **Reference `uri` schemes (v1):** Allowlist `https:` (production fetch) and `fixture:` (tests only). Content addressing via mandatory `payload_hash`, not a separate CAS URI scheme in v1.
4. **IG/WG home:** Enter via existing **Security Interest Group** (`#security-ig`); scope already includes auditability/observability. Distinguish from SEP-2809 ATSA (server admission). Propose a new IG via `#wg-ig-group-creation` only if Security IG declines. No charter is claimed yet; `experimental-ext-*` still needs IG/WG association + sponsor.

---

## Acceptance criteria for “industry standard” (our bar)

- [ ] Thesis locks hold in spec + tests
- [x] Wire spec complete; open questions closed (2026-09-06)
- [ ] Conformance scenarios implemented and green against a reference server/client
- [ ] External emitter can pass without AgentStatus credentials
- [ ] MCP community path started (Security IG discussion or experimental-ext proposal with sponsor)
- [ ] Only then: conformance PR that adds **extension scenarios**, not docs

---

## References

- SEP-2133 Extensions  
- SEP-2575 Make MCP Stateless (`2026-07-28`)  
- SEP-2663 / Tasks extension (advertise + conformance quality bar)  
- MCP `2026-07-28` error taxonomy (basic protocol)  
- Security IG charter (auditability / observability; related ATSA SEP-2809)  
- `toa/0.1` SPEC and schema in this repository  
- modelcontextprotocol/conformance#479 maintainer note  
- [`DECISIONS.md`](./DECISIONS.md)