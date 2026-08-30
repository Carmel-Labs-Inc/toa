# Complementarity: MCPJam-style pre-prod checks and TOA

TOA is not a substitute for Inspector, OAuth conformance, or host/model evals. It covers a different axis: **did the tool reply actually deliver?**

## What pre-prod platforms already do well

Typical MCPJam CLI surfaces (doctor, protocol conformance, tools call, evals):

- Connectivity and initialize
- Tools / resources / prompts discovery
- **Input** schema validity (`tools-input-schemas-valid`)
- OAuth / host compatibility / LLM evals (right tool, right args)

Live trial note (public DeepWiki MCP, Aug 2026): doctor reported tools **discovered**; protocol profile still listed `modern-tool-output-schema-conformant` among **pending / unscored** checks. `tools call --expect-success` evaluates the MCP error envelope, not AgentStatus-style functional/shape grades.

## What TOA adds

| Axis | Pre-prod platform | TOA |
|---|---|---|
| When | Before ship (CI / local) | CI **and** continuous prod emit |
| Protocol / OAuth | Strong | Out of scope |
| Host/model behavior | Evals | Out of scope |
| Server delivery after `tools/call` | Thin / pending | `functional`, `shape`, … |
| Artifact | JSON / JUnit | Signed `toa/0.1` |

## Suggested CI sandwich

```text
doctor + protocol conformance + (optional) evals
        +
toa-verify --require-layer functional=pass
        →
promote / merge
```

Either verify an AgentStatus-emitted TOA, or emit `toa/0.1` from your own delivery checks with your own key.
