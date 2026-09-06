# MCP Extension track (incubating)

> **Status:** Draft / incubating on Carmel Labs.  
> **Not** an official MCP extension. **Not** an `experimental-ext-*` repo under `modelcontextprotocol` (yet).

This directory is the **industry-standard path** for Tool Outcome Attestation as a *negotiated MCP capability*, following [SEP-2133](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md).

The parent repository still owns the portable evidence format (`toa/0.1`) and offline verify libraries. This track owns negotiation, wire binding, SEP, and conformance.

## Read in order

1. [`THESIS.md`](./THESIS.md) — locked product/protocol decisions (do not violate in code)
2. [`SEP-DRAFT.md`](./SEP-DRAFT.md) — Extensions Track SEP draft
3. [`specification/draft/toa-extension.md`](./specification/draft/toa-extension.md) — RFC 2119 wire spec
4. [`DECISIONS.md`](./DECISIONS.md) — dated decisions closing open questions
5. [`conformance/SCENARIOS.md`](./conformance/SCENARIOS.md) — Tasks-quality scenario plan
6. [`docs/security-ig-outreach.md`](./docs/security-ig-outreach.md) — Security IG Discord / Discussion draft

## Extension ID

```text
dev.agentstatus/toa
```

Per SEP-2133: reversed-domain vendor prefix. Owning `agentstatus.dev` → `dev.agentstatus/toa`. Not `agentstatus.dev/toa`. Product URL MAY be `https://agentstatus.dev/toa`.

Graduation to `io.modelcontextprotocol/toa` requires MCP governance acceptance — not a rename PR.

## Why this exists

`modelcontextprotocol/conformance#479` (docs-only optional `toa-verify`) was closed in a maintainer backlog sweep with guidance to propose an **extension with conformance tests**. That guidance is correct. This tree is that work.

## What “done” means (no vibe MVP)

- [x] Thesis locks reviewed and held
- [x] Wire spec open questions closed — see [`DECISIONS.md`](./DECISIONS.md)
- [x] Golden fixtures + Python `toa_ext` binding validate
- [x] Conformance harness T1–T10 (in-process) — **10/10 PASS**
- [x] Reference attach path (`toa_ext.attach` + MCP SDK `ToaAttachExtension`)
- [x] Full E2E vs official MCP Python SDK 2.1+ (2026-07-28 advertise/attach/require/fail-closed + stdio subprocess) — `python/tests/test_e2e_mcp_sdk.py`
- [ ] Security IG review (outreach draft ready; post when you want)
- [ ] Official MCP conformance PR (`--suite extensions`) after IG path

## Relationship to AgentStatus

AgentStatus is a `third_party` emitter and observation network. Verify remains offline and emitter-agnostic. The extension must not require an AgentStatus account.
