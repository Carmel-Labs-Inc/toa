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
