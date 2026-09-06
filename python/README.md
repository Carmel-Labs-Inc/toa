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

Validates `dev.agentstatus/toa` AttestationBinding objects (reuse of `toa_verify` for signatures):

```bash
cd python && pip install -e ".[dev]"
pytest tests/test_binding.py -q
```

Conformance golden fixtures live in `../mcp-extension/conformance/fixtures/`.
