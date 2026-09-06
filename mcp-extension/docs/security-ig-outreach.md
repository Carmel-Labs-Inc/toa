# Security IG outreach — TOA

Draft for `#security-ig`. Post after E2E is green. Don’t claim sponsorship.

Discord: https://discord.com/channels/1358869848138059966/1379811011669921883  
Repo: https://github.com/Carmel-Labs-Inc/toa

---

## Discord (use this)

```text
Hey — sharing incubating work on tool outcome attestation for MCP, looking for Security IG eyes when you have bandwidth.

Problem: MCP made tool calls interoperable, but “RPC succeeded” still isn’t “the tool delivered.” Empty prose, soft errors in content, schema drift, broken multi-step flows can all look fine on the wire. Gateways and hosts don’t have a shared, negotiable way to require attested outcomes.

What we have (Apache-2.0):

1. toa/0.1 — portable signed evidence doc (graded layers: reach → invoke → functional → …). Offline verify against a pinned emitter + key. No account needed to verify.
2. Optional MCP extension `dev.agentstatus/toa` (SEP-2133 reverse-DNS for agentstatus.dev). Clients can require / servers-or-observers can attach that evidence on tools/call results via _meta. Trust is role-pinned (third_party | observer | server); server self-attest is allowed but not the default trust root.

Where this sits: Security IG already covers auditability / tamper-evident records of what a tool call did. That’s the home for this. We’re not asking to invent a new IG for it.

Relative to ATSA (SEP-2809): complementary, not competing.
- ATSA = admit the server before dispatch
- TOA = attest tool-call delivery outcome after/around the call
Both can coexist (admit with ATSA, require TOA for high-assurance promote/CI).

We’re past docs-only. Spec + SEP draft + conformance harness + reference attach path live here, including E2E against the official MCP Python SDK (2026-07-28 negotiate → attach → require → fail-closed):
https://github.com/Carmel-Labs-Inc/toa/tree/main/mcp-extension

Not asking for official status or experimental-ext yet. Want blunt review of the draft and whether the Security IG backlog is the right place to track it next to ATSA so the two don’t get conflated.
```

---

## After you post

- [ ] Paste into `#security-ig`
- [ ] Optional GitHub Discussion with the same framing
- [ ] Save the thread URL in DECISIONS / contribution tracking

## Don’t

- Refile docs-only conformance PRs
- Claim IG sponsorship before they say so
- Pitch product pricing in IG channels
