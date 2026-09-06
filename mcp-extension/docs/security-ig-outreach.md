# Security IG outreach — Tool Outcome Attestation (TOA)

**Status:** draft for posting (not posted yet)  
**Date:** 2026-09-06  
**Target:** MCP Security Interest Group (`#security-ig`)  
**Facilitators:** Den Delimarsky (`@localden`), Paul Carleton (`@pcarleton`)  
**Charter:** [Security IG](https://modelcontextprotocol.io/community/interest-groups/security)  
**Notes category:** [Meeting Notes - Security IG](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/categories/meeting-notes-security-ig)

---

## Why this group

Security IG scope already includes **auditability and observability** (“tamper-evident records of what a tool call did”) and **server identity / attestation / admission**. TOA is the *outcome* half of that story, complementary to admission.

Paul closed docs-only [conformance#479](https://github.com/modelcontextprotocol/conformance/pull/479) with: propose an extension + conformance tests. That is the path we are on.

---

## Discord post (short)

**Suggested channel:** `#security-ig`  
**Tone:** problem + distinction from ATSA + ask for agenda slot — not a product pitch.

```text
Hi Security IG — looking for a brief agenda slot / feedback on incubating work.

Problem: MCP protocol success (JSON-RPC ok / HTTP 200) is not tool *delivery* success. Empty prose, soft-error content, schema drift, and broken multi-step handles still look “successful.” Gateways and hosts have no shared, negotiable way to require attested outcomes.

Proposal (incubating, vendor-prefixed): MCP extension `dev.agentstatus/toa` (SEP-2133 reverse-DNS for agentstatus.dev) that negotiates attach/require of a portable signed `toa/0.1` evidence document on tools/call results. Trust is pinned to emitter role (third_party | observer | server) + key — not “signature present.” Offline verify; no vendor account required to verify.

Deliberately complementary to SEP-2809 ATSA:
- ATSA = admit the *server* before dispatch (identity / clearance)
- TOA = attest the *tool call outcome* after/around delivery

Artifacts (Apache-2.0):
- Evidence + verify: https://github.com/Carmel-Labs-Inc/toa
- Extension thesis / SEP draft / wire spec / T1–T10 harness:
  https://github.com/Carmel-Labs-Inc/toa/tree/main/mcp-extension

Ask: (1) Is outcome attestation in Security IG scope vs a new IG?
(2) Interest in reviewing the SEP draft before any experimental-ext request?
(3) How you want this distinguished from ATSA in the IG backlog?

Happy to take hard feedback. Not asking for official status yet.
```

---

## GitHub Discussion post (longer, optional)

**Category:** preferably a Security IG discussion, or new thread linked from `#security-ig`  
**Title:** Incubating extension: Tool Outcome Attestation (`dev.agentstatus/toa`) — feedback requested

### Body

## Summary

We are incubating an optional MCP extension for **negotiated tool-outcome attestation**, following SEP-2133. This note asks Security IG whether the problem belongs here, how it should sit next to SEP-2809 (ATSA), and whether the draft is worth an office-hours review.

## Problem

MCP makes tool invocation interoperable. It does not define a shared artifact for whether delivery *succeeded* in an operationally meaningful sense. Today, stacks treat JSON-RPC success, HTTP 200, or server self-declarations as proxies. Those proxies fail open for empty/soft-error payloads and fail closed too late for gateways that need evidence.

## What we are *not* proposing

- Not docs-only “run `toa-verify` after conformance” (already tried; correctly closed in conformance#479).
- Not replacing ATSA / server admission.
- Not requiring an AgentStatus account to verify.
- Not treating server self-attestation as the default trust root.

## What we are proposing

1. Portable evidence format `toa/0.1` (already open): signed graded layers (reach → invoke → functional → …).
2. MCP extension id `dev.agentstatus/toa`: client can `require` attested bindings; server/observer can `attach` on `tools/call` results via `_meta`.
3. Conformance scenarios T1–T10 (negotiation, attach, fail-closed, role pinning, signature/age/hash).
4. Later: IG sponsorship → experimental-ext → official `io.modelcontextprotocol/*` only via SEP acceptance.

Repo: https://github.com/Carmel-Labs-Inc/toa (`mcp-extension/` for the protocol track).

## Relation to SEP-2809 ATSA

| | ATSA (SEP-2809) | TOA (`dev.agentstatus/toa`) |
|---|---|---|
| When | Before dispatch | On / after tool result |
| Object | Server identity / clearance | Tool call delivery outcome |
| Trust question | “Is this server admitted?” | “Did this call deliver, per a pinned emitter?” |

Both can coexist: admit with ATSA, require TOA outcomes for promote/CI/high-assurance clients.

## Asks for Security IG

1. Confirm scope: auditability / outcome evidence under Security IG vs elsewhere.
2. 15–20 min office-hours review of thesis + wire draft.
3. Guidance on experimental-ext timing (after reference SDK path is solid).

## Non-goals for this message

Merging into core MCP. Renaming to `io.modelcontextprotocol/toa` unilaterally. Product placement for AgentStatus monitoring.

---

## Talking points if Paul / Den push back

- **“This is vendor promo.”** Extension is vendor-*prefixed* by SEP-2133 rules while incubating; verify is offline and emitter-agnostic; AgentStatus is one possible `third_party` emitter.
- **“Use ATSA.”** Different threat: admission ≠ outcome. Soft-fail tool bodies pass admission.
- **“Self-sign on the server.”** Thesis L1: `server` role allowed but not default trust; conformance T4 rejects `server` when client does not accept it.
- **“Come back with experimental-ext.”** Need IG association first per SEP-2133; that is why we are here.

## After posting

- [ ] Paste Discord message in `#security-ig`
- [ ] Optional: open GitHub Discussion; link Discord ↔ Discussion
- [ ] Add agenda ask for next Security IG office hours
- [ ] Update `DECISIONS.md` / contribution targets with discussion URL when live

## Do not

- Refile docs-only PRs to `modelcontextprotocol/conformance`
- Claim Security IG sponsorship before they say so
- Pitch Fabric pricing in IG channels (antitrust / CoC)
