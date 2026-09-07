# TOA MCP Extension — Decisions Log

Dated decisions that close open questions. Wire behavior is normative in
[`specification/draft/toa-extension.md`](./specification/draft/toa-extension.md).
Thesis locks remain in [`THESIS.md`](./THESIS.md).

---

## 2026-09-06 — Close open questions (v1 wire freeze basis)

### D1 — Extension identifier naming (SEP-2133)

**Decision:** Wire extension ID remains `dev.agentstatus/toa`.

**Rationale:** SEP-2133 requires `{vendor-prefix}/{extension-name}` where the vendor
prefix SHOULD be a **reversed domain name** the author owns. Carmel / AgentStatus owns
`agentstatus.dev`, so the prefix is `dev.agentstatus`, not the hostname string
`agentstatus.dev`. Literal `agentstatus.dev/toa` is **not** a valid extension identifier
(hostname-shaped prefixes violate the reversed-domain convention and `_meta` key naming
used by extensions). Product and docs URLs MAY still use `https://agentstatus.dev/toa`.

**Confidence:** high (SEP-2133 text is explicit).

---

### D2 — Error when `require` is unmet

**Decision:** Use application-defined JSON-RPC error:

| Field | Value |
|---|---|
| **code** | `-38100` |
| **name** | `ToaAttestationFailure` |
| **message** | `TOA attestation required` or `TOA attestation invalid` |
| **data** | `{ "extensionId": "dev.agentstatus/toa", "reason": <enum> }` |

**Do not use:**

- `-32071` (provisional in earlier draft) — falls in MCP-reserved `-32020`..`-32099`
- `-32021` / `MissingRequiredClientCapability` — wrong polarity (server needs undeclared
  *client* capability; TOA `require` is client demanding attested *server* results)

**Where it applies:**

- **Server-emitted:** when the client advertised `require: true` and the server
  (`attach: on_require` or `always`) cannot return a successful `tools/call` with a
  binding that would satisfy client settings.
- **Client-local:** when the client receives a successful `tools/call` result under
  `require: true` with missing/invalid binding, the client MUST fail closed locally.
  That local rejection is not required to be a peer JSON-RPC error; if surfaced in
  JSON-RPC-shaped structures, it MUST use the same code/name/data shape and MUST NOT
  be confused with a peer response.

**Migration path:** If a future MCP SEP allocates a core or official-extension code for
“required extension constraint unmet,” implementations of a later wire revision MAY
accept that code in addition to `-38100` for one revision, then drop `-38100` only under
a new extension id (SEP-2133 breaking-change rule). Until then, `-38100` is normative for
`dev.agentstatus/toa`.

**Confidence:** high on not using reserved/MCP taxonomy codes; moderate on exact
application code number (band is justified; number is ours until official allocation).

---

### D3 — Advertising channel (protocol revision)

**Decision:** Primary target protocol revision is **`2026-07-28`** (SEP-2575 stateless
model + SEP-2133 `extensions` field).

| Side | Normative advertise channel |
|---|---|
| Client | Per-request `params._meta["io.modelcontextprotocol/clientCapabilities"].extensions["dev.agentstatus/toa"]` |
| Server | `server/discover` result `capabilities.extensions["dev.agentstatus/toa"]` |

Session/`initialize` capability advertisement is **not** the primary path: `2026-07-28`
removes the initialize handshake; capabilities MUST NOT be inferred across requests.

**Compatibility note (non-normative for v1):** Hosts still speaking `2025-11-25` MAY map
the same settings objects onto that revision’s `initialize` capability objects for
prototyping. Conformance for this incubating extension is defined against `2026-07-28`.

**Confidence:** high (Tasks / SEP-2663 and SEP-2575 match this pattern).

---

### D4 — Reference-mode `uri` schemes (v1 allowlist)

**Decision:** Normative allowlist for `mode: "reference"`:

| Scheme | Role |
|---|---|
| `https:` | Production and online fetch. Validators that fetch MUST apply SSRF / allowlist controls. |
| `fixture:` | Conformance and local tests only (`fixture:<name>` → named document in a test store). MUST NOT be treated as a production trust source unless the implementation is explicitly in test mode. |

**Not in v1 allowlist:** `http:`, `file:`, `toa+https:`, IPFS/`ipfs:`, or other
content-addressed URI schemes.

**Content addressing:** Provided by mandatory `payload_hash` on every reference binding,
not by a separate URI scheme. Validators MAY resolve from a pre-supplied store keyed by
hash without network I/O; when a fetch occurs, the URI scheme MUST still be allowlisted
and the resolved document MUST match `payload_hash`.

**Confidence:** high for https + hash; moderate that future CAS schemes stay out of v1.

---

### D5 — MCP community IG/WG home

**Decision:** Do **not** invent a charter. Recommended path:

1. **Enter via existing Security Interest Group** (`#security-ig` on MCP Contributors
   Discord). Security IG scope already includes *auditability and observability*
   (tamper-evident records of what a tool call did). Facilitators currently include
   Den Delimarsky and Paul Carleton.
2. Present TOA as **tool delivery outcome attestation**, distinct from agenda item
   SEP-2809 *Attested Tool-Server Admission (ATSA)* (server admission ≠ outcome grades).
3. Ask Security IG to validate problem/use cases and recommend either:
   - continued incubation under Security IG sponsorship toward `experimental-ext-*`, or
   - a **new Working Group** once deliverables (SEP + reference impl) are concrete.
4. **Only if** Security IG declines scope or bandwidth: propose a **new Interest Group**
   via Discord `#wg-ig-group-creation` per community process (requires Core Maintainer /
   Lead Maintainer sponsorship). That proposal does not exist yet; do not claim an IG.

Until an IG/WG association and sponsor exist, remain incubating on
`Carmel-Labs-Inc/toa` with vendor prefix `dev.agentstatus`. SEP-2133
`experimental-ext-*` under the MCP org requires an associated IG/WG.

**Confidence:** high on process honesty; moderate on whether Security IG ultimately
sponsors vs diverting to a new IG (community decision, not ours to pre-claim).

---

## 2026-09-07 — Absence / negative-outcome gap (issue #3350 feedback)

### D5 — NegotiationRecord + signed negatives

**Decision:** Close the “absence carries no information” gap before treating the
extension as implementable for offline/post-hoc use:

1. **NegotiationRecord (`toa-negotiation/0.1`)** — clients/gateways MUST persist
   whether the server advertised `dev.agentstatus/toa` at capability exchange.
2. **Signed negative outcomes** — servers with `attach: on_require|always` MUST
   attach bindings on failure/refuse paths, not only happy path. Additive signed
   `disposition` on `toa/0.1`: `delivered` | `failed` | `refused` | `unavailable`.
3. Offline verifiers MUST distinguish `outside_toa` vs `attestation_gap`.

**Implementation (2026-09-07):** `toa_ext.negotiation` (`build_negotiation_record`,
`classify_absence`), `ToaAttachExtension` attaches on `is_error` with
`disposition=failed`, harness T11–T13 PASS, SDK E2E negative-path test green.

**Rationale:** Without these, silence after an incident is ambiguous and incentives
favor stopping attestation when things break. Feedback on
modelcontextprotocol/modelcontextprotocol#3350.

**Confidence:** high on the problem; high on the fix shape.

**Issue reply:** draft only when author approves; do not post until then.
