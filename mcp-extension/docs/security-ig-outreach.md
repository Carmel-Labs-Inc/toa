# Security IG submission — TOA

Not a permission ask. The work is delivered. Post this after the SEP PR is open (or with the compare link if GitHub needs a one-click confirm).

Discord: https://discord.com/channels/1358869848138059966/1379811011669921883  
SEP branch (open PR): https://github.com/modelcontextprotocol/modelcontextprotocol/compare/main...dulrajnr:mcp-sep-toa:sep/tool-outcome-attestation?quick_pull=1  
Reference impl: https://github.com/Carmel-Labs-Inc/toa  
SEP text in-repo: https://github.com/Carmel-Labs-Inc/toa/blob/main/mcp-extension/seps/0000-tool-outcome-attestation.md

---

## Discord (use this)

```text
Submitted an Extensions Track SEP for Tool Outcome Attestation and posting it here for Security IG tracking next to ATSA.

Problem: MCP tool RPC success still isn’t delivery success. Empty prose, soft errors in content, schema drift, broken multi-step flows can all look fine on the wire. There’s been no shared, negotiable way to require attested outcomes.

What’s delivered (not a sketch):

1. toa/0.1 — portable signed evidence (graded layers). Offline verify. Pin emitter + key. No vendor account required to verify.
2. Extension `dev.agentstatus/toa` (SEP-2133 reverse-DNS for agentstatus.dev) — clients require / servers-or-observers attach on tools/call `_meta`. Role-pinned trust (third_party | observer | server); server self-attest is not the default trust root.
3. Reference implementation + conformance T1–T10 + full E2E on the official MCP Python SDK 2.1 (2026-07-28 discover → attach → require → fail-closed, including stdio subprocess).

Positioning vs ATSA (SEP-2809): complementary.
- ATSA = admit the server before dispatch
- TOA = attest tool-call delivery outcome
Both can run together.

Security IG is the right home (auditability / tamper-evident records of what a tool call did). Not proposing a new IG.

SEP: https://github.com/modelcontextprotocol/modelcontextprotocol/compare/main...dulrajnr:mcp-sep-toa:sep/tool-outcome-attestation?quick_pull=1
Impl: https://github.com/Carmel-Labs-Inc/toa/tree/main/mcp-extension

Looking for a sponsor per the SEP workflow. Happy to take technical objections on the draft.
```

---

## After SEP PR number exists

Replace the compare URL in the Discord text with the real `https://github.com/modelcontextprotocol/modelcontextprotocol/pull/NNNN` link.

## Don’t

- Soften this into “is it okay if we…?”
- Refile docs-only conformance PRs
- Pitch product pricing in IG channels
