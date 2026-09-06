# Security IG outreach — TOA

Draft for `#security-ig`. Post when ready. Don’t claim sponsorship.

Discord: https://discord.com/channels/1358869848138059966/1379811011669921883  
Charter: https://modelcontextprotocol.io/community/interest-groups/security  
Repo: https://github.com/Carmel-Labs-Inc/toa

---

## Discord (use this)

```text
Hey — wanted to float something for feedback / maybe an office hours slot if it fits.

Short version: MCP makes calling tools interoperable, but “RPC succeeded” still isn’t the same as “the tool actually delivered.” Empty prose, soft errors in content, schema drift, broken multi-step flows… all can look fine on the wire. Gateways and hosts don’t have a shared way to say “I require attested outcomes.”

We’ve been incubating two pieces (Apache-2.0):

1. toa/0.1 — small signed evidence doc (graded layers: reach → invoke → functional → …). Offline verify, pin the emitter + key. No account needed to verify.
2. Optional MCP extension `dev.agentstatus/toa` (SEP-2133 reverse-DNS for agentstatus.dev) so clients can require / servers-or-observers can attach that evidence on tools/call results via _meta. Trust is role-pinned (third_party | observer | server) — server self-attest is allowed but not the default happy path.

This is intentionally next to ATSA (SEP-2809), not a replacement:
- ATSA ≈ admit the server before you talk to it
- TOA ≈ attest what a tool call actually delivered

Docs/spec/harness are in the repo under mcp-extension/:
https://github.com/Carmel-Labs-Inc/toa/tree/main/mcp-extension

Questions for the IG:
1. Does outcome / delivery attestation sit under Security IG (auditability), or should this live elsewhere?
2. Worth a quick review of the draft before we even think about experimental-ext?
3. Any guidance on how you want this tracked relative to ATSA so we don’t confuse the two?

Not asking for official anything yet. Happy to take blunt feedback.
```

---

## Longer GitHub Discussion (optional)

**Title:** Incubating: tool outcome attestation (`dev.agentstatus/toa`)

### Body

We’ve been working on a gap that keeps biting people in production MCP stacks: protocol success isn’t delivery success. A `tools/call` can return empty text, a soft error wrapped as content, or a broken handoff and still look like a clean RPC.

What exists today:

- `toa/0.1` — portable signed JSON with graded delivery layers. Verify offline against a pinned emitter key. Spec + python/js verify in https://github.com/Carmel-Labs-Inc/toa
- Draft MCP extension `dev.agentstatus/toa` — negotiate attach/require of that evidence on `tools/call` results. Thesis, SEP draft, wire spec, and T1–T10 conformance harness under `mcp-extension/`

What this is not:

- Not a docs-only “run verify after CI” tip (that approach already got pushed back on in conformance, correctly — needs a real extension + tests)
- Not ATSA / server admission (SEP-2809). Different moment in the lifecycle.
- Not “trust whatever the server signs about itself” by default
- Not tied to an AgentStatus login for verify

Why Security IG: charter already covers auditability / tamper-evident records of what a tool call did. We’re asking whether outcome attestation belongs here, and whether the draft is worth an office-hours pass before any `experimental-ext-*` ask.

Happy to adjust scope, naming, or trust model based on IG feedback.

---

## After you post

- [ ] Paste Discord version in `#security-ig`
- [ ] Optional Discussion; link the two
- [ ] Drop the thread URL into DECISIONS / contribution tracking when you have it

## Don’t

- Refile docs-only conformance PRs
- Say the IG “sponsors” this before they do
- Pitch product pricing in IG channels
