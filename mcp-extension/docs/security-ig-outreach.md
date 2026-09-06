# Security IG submission — TOA

Submitted. Public tracker:

**Issue:** https://github.com/modelcontextprotocol/modelcontextprotocol/issues/3350  
**SEP branch:** https://github.com/dulrajnr/mcp-sep-toa/tree/sep/tool-outcome-attestation  
**Impl:** https://github.com/Carmel-Labs-Inc/toa  

Direct PRs into `modelcontextprotocol/modelcontextprotocol` are limited to collaborators. Collaborator is **invite-only** (owners add you); you cannot self-join. Path: Discord + this issue until a collaborator opens the SEP PR or invites.

Discord: https://discord.com/channels/1358869848138059966/1379811011669921883

---

## Discord (use this)

```text
Submitted an Extensions Track SEP for Tool Outcome Attestation. Tracking issue (PRs into the spec repo are collaborator-only right now):

https://github.com/modelcontextprotocol/modelcontextprotocol/issues/3350

Problem: MCP tool RPC success still isn’t delivery success. Empty prose, soft errors in content, schema drift, broken multi-step flows can all look fine on the wire. There’s been no shared, negotiable way to require attested outcomes.

What’s delivered:

1. toa/0.1 — portable signed evidence (graded layers). Offline verify. Pin emitter + key. No vendor account required to verify.
2. Extension `dev.agentstatus/toa` (SEP-2133 reverse-DNS for agentstatus.dev) — clients require / servers-or-observers attach on tools/call `_meta`. Role-pinned trust (third_party | observer | server); server self-attest is not the default trust root.
3. Reference implementation + conformance T1–T10 + full E2E on the official MCP Python SDK 2.1 (2026-07-28 discover → attach → require → fail-closed, including stdio subprocess).

Positioning vs ATSA (SEP-2809): complementary.
- ATSA = admit the server before dispatch
- TOA = attest tool-call delivery outcome
Both can run together.

Security IG is the right home (auditability). SEP branch ready for a collaborator to open the PR into `seps/`:
https://github.com/dulrajnr/mcp-sep-toa/tree/sep/tool-outcome-attestation

Looking for a sponsor per the SEP workflow. Happy to take technical objections on the draft.
```
