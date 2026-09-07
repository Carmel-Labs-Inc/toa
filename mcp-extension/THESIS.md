# TOA MCP Extension — Locked Thesis

**Status:** incubating design lock (2026-09-06)  
**Goal:** industry-standard *negotiated* outcome verification on MCP — not a CI docs plug, not a vibe MVP.

This document is the product/protocol contract. The SEP and wire spec must obey it. If a proposed feature violates a lock below, change this file first in an explicit decision, do not silently diverge in code.

---

## 1. Two artifacts, one fight

| Artifact | What it is | Repo path |
|---|---|---|
| **Evidence format** (`toa/0.1`) | Portable signed JSON: an emitter graded a tool delivery | `../schema`, `../SPEC.md`, verify libs |
| **MCP extension** (`dev.agentstatus/toa`) | Optional capability negotiation + wire binding so clients/servers/gateways can *require or attach* that evidence on MCP sessions | `./` (this tree) |

The fight is **outcome verification**. The evidence format alone is necessary but not sufficient for industry standard status. Negotiation makes “I require attested outcomes” a first-class MCP capability.

Paul Carleton’s close of [conformance#479](https://github.com/modelcontextprotocol/conformance/pull/479) is correct for docs-only: conformance absorbs **extensions with tests**, not README plugs.

---

## 2. Non-negotiable locks

### L1 — Third-party honesty over self-attestation

Server-signed “I worked” is the failure mode TOA exists to escape. The extension MUST:

- Distinguish **emitter roles**: `third_party` | `observer` | `server`
- Allow verifiers / clients to **require** role + `emitter.name` + public key
- NEVER define “signature valid” alone as “outcome verified for trust decisions”

Self-attestation (`server` role) MAY exist for debugging. It MUST NOT be the default trust root in normative examples or conformance “happy path” gates.

### L2 — Evidence schema stays off-core-protocol

`toa/0.1` remains a **portable document** with its own schema and verify algorithm. The MCP extension does not fork a second grading vocabulary. Wire bindings reference or embed `toa/0.1` documents.

Breaking evidence changes → new `toa/0.x` (or later) per existing schema rules.  
Breaking wire negotiation → new extension id (`…/toa-v2`) per SEP-2133.

### L3 — Negotiation is real behavior, not a flag

Advertising `dev.agentstatus/toa` without attaching or honoring `require` is non-conformant.

Minimum behaviors:

- Server that advertises the extension MUST be able to attach a binding when policy says so
- Client that sets `require: true` MUST cause missing/invalid bindings to fail closed (defined error), not silently accept bare `tools/call` success
- Parties that do not negotiate MUST interoperate on core MCP (graceful degradation)

### L4 — AgentStatus is an emitter, not the protocol

- Wire extension id MUST remain `dev.agentstatus/toa` while incubating
- Per SEP-2133, vendor prefixes are **reversed domain names**: owning `agentstatus.dev` → prefix `dev.agentstatus` → id `dev.agentstatus/toa`. Literal `agentstatus.dev/toa` is **not** a valid extension identifier. Product/docs URL MAY still be `https://agentstatus.dev/toa`
- Verify MUST work offline against pinned public keys (already true for `toa/0.1`)
- No AgentStatus account, API key, or network call is required to verify
- Other emitters are first-class if they sign `toa/0.1` with their own keys

Aspiration to `io.modelcontextprotocol/toa` is a **later MCP governance outcome**, not a rename we perform unilaterally.

### L5 — Fabric / distributed observation stays complementary

Capability negotiation does not create cross-host wild evidence. Fabric Live + AgentStatus Intelligence remain the distribution/observation plane. The extension standardizes how sessions and gateways **speak about** attested outcomes; it does not replace residential/passive capture.

### L7 — Absence must be interpretable

Offline verifiers MUST be able to distinguish “server never advertised TOA” from
“server advertised TOA but produced no attestation for this call.” Clients persist
NegotiationRecords (`toa-negotiation/0.1`). Servers that advertise attach MUST emit
signed negative outcomes (disposition / failing layers), not silence on failure.

---

## 3. What is negotiated (normative intent)

### Extension identifier

```text
dev.agentstatus/toa
```

SEP-2133 format `{reversed-domain}/{name}`. Not `agentstatus.dev/toa`. See [`DECISIONS.md`](./DECISIONS.md) D1.

### Client settings (capability value object)

```json
{
  "require": false,
  "acceptedEmitterRoles": ["third_party", "observer"],
  "requireEmitter": null,
  "maxAgeSeconds": 604800,
  "minLayers": {
    "reach": "pass",
    "invoke": "pass",
    "functional": "pass"
  }
}
```

- `require: true` → fail closed without a binding that verifies under these constraints
- `acceptedEmitterRoles` defaults MUST NOT silently include `server` in security-sensitive profiles (gateways SHOULD set explicitly)

### Server settings (capability value object)

```json
{
  "supportedEmitterRoles": ["third_party", "observer", "server"],
  "attach": "on_require"
}
```

- `attach`: `never` | `on_require` | `always`
- A pure verify-only gateway may advertise client-side require without being an emitter

### Wire binding

On `tools/call` **result** `_meta`:

```text
_meta["dev.agentstatus/toa"] = AttestationBinding
```

`AttestationBinding` is either:

1. **embedded** — full `toa/0.1` document (size-sensitive; allowed)
2. **reference** — `{ "mode": "reference", "uri": "...", "payload_hash": "sha256:...", "emitter": {...}, "emitter_role": "..." }`  
   Fetch is optional for online verifiers; **hash + signature verify** of the resolved document is mandatory when validating

Binding applies to the **tool call outcome represented by that result**, not to catalog listing or initialize.

---

## 4. Industry path (ordered, no shortcuts)

1. Lock thesis (this file) + RFC 2119 wire spec + SEP draft in `Carmel-Labs-Inc/toa`
2. Reference behaviors: attach binding, verify binding, fail closed on `require`
3. Conformance scenarios (Tasks-quality): negotiation, attach, require, role pinning, degradation
4. At least one SDK reference implementation path (TypeScript or Python) that is real, not sample YAML
5. Interest Group / Working Group engagement under MCP community process
6. Experimental extension repo under MCP org only with WG charter (SEP-2133)
7. Official `io.modelcontextprotocol/toa` only via Extensions Track SEP acceptance
8. Re-approach `modelcontextprotocol/conformance` with **extension scenarios**, not docs

Skip any step and you get another closed backlog PR.

---

## 5. Success criteria

**Users (MCP authors, platform eng, gateways):**

- Can require attested tool outcomes in capability language hosts understand
- Can pin trust to emitter role + key, not “the server said so”
- Can verify offline

**Us (AgentStatus / Carmel):**

- Outcome verification becomes negotiable industry vocabulary
- AgentStatus remains a high-quality `third_party` emitter without being a protocol chokepoint
- Fabric Live remains the wild-evidence advantage; extension is the standard socket it plugs into

**Not success:**

- Merged README in conformance
- Stars on a toy demo host that self-signs every `tools/call`
