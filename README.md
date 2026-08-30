# Tool Outcome Attestation (TOA)

Open **schema + verify libraries** for MCP tool-delivery evidence (`toa/0.1`).

Apache-2.0. Maintained by [Carmel Labs](https://carmel.so) / [AgentStatus](https://agentstatus.dev).

## What this is

A small signed JSON document that records whether a tool **actually delivered** (reach → invoke → functional → shape → …), so CI and gateways can gate on something sharper than `HTTP 200` / `success: true`.

## What this is not

- Not a replacement for MCP / A2A
- Not continuous production monitoring (that stays on AgentStatus)
- Not a self-attestation format for MCP servers

## Quick start

### Verify offline (Python)

```bash
cd python && pip install -e .
toa-verify ../examples/signed-example.json \
  --require-emitter agentstatus \
  --require-layer functional=pass
```

### Verify offline (Node 18+)

```bash
cd javascript
node src/cli.js ../examples/signed-example.json \
  --require-emitter agentstatus \
  --require-layer functional=pass
```

### Verify via AgentStatus API

```bash
curl -sS -X POST https://api.agentstatus.dev/api/rora/public/toa/verify \
  -H 'content-type: application/json' \
  -d @examples/verify-request.json
```

## Layout

| Path | Purpose |
|---|---|
| [`SPEC.md`](./SPEC.md) | Spec text |
| [`schema/toa-0.1.schema.json`](./schema/toa-0.1.schema.json) | JSON Schema |
| [`keys/`](./keys/) | AgentStatus public keys only |
| [`python/`](./python/) | `toa-verify` reference implementation |
| [`javascript/`](./javascript/) | Node verify + CLI |
| [`examples/`](./examples/) | Sample docs + CI snippet |

## How people use it

1. **CI** — fail the PR unless a signed TOA verifies and `layers.functional == pass`
2. **Gateways / registries** — require a recent valid TOA before promoting a wrapper
3. **AgentStatus customers** — emit via the product API, hand the JSON to (1) or (2)

See [`examples/github-action/`](./examples/github-action/) for a starter workflow.

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE).
