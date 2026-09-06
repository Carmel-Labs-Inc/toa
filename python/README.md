# toa-verify (Python)

```bash
cd python
pip install -e .
toa-verify ../examples/unsigned-example.json   # fails: no signature
```

Offline verify against the AgentStatus `v1` public key in `../keys/agentstatus-v1.json`.

```bash
toa-verify path/to/signed.toa.json \
  --require-emitter agentstatus \
  --require-layer functional=pass \
  --max-age 7d
```

## MCP extension binding (`toa_ext`)

Validates `dev.agentstatus/toa` AttestationBinding objects and provides a **reference attach path** (sign → `_meta` binding → require enforcement), plus an official MCP Python SDK Extension (`ToaAttachExtension`).

```bash
cd python && pip install -e ".[dev,e2e]"
pytest tests/ -q
# includes FakeMcp harness scenarios via unit tests + real SDK E2E (in-process + stdio)
pytest tests/test_e2e_mcp_sdk.py -v
```

Conformance golden fixtures live in `../mcp-extension/conformance/fixtures/`.
Security IG outreach draft: `../mcp-extension/docs/security-ig-outreach.md`.
