# Conformance golden fixtures (`toa/0.1`)

Test emitter: **`toa-conformance`** / `key_id: test-v1`  
Ed25519 keypair under [`keys/`](./keys/).

| Document | Purpose |
|---|---|
| `pass_functional.json` | Happy path: `functional=pass`, tool `echo`, fresh `observed_at` |
| `fail_functional.json` | T6: `functional=fail` |
| `expired.json` | T7: old `observed_at` (`2020-01-01`) |
| `wrong_tool.json` | Tool correlation: `tool.name=other_tool` |
| `server_role.json` | T4: same grades as pass; use with binding `emitter_role: server` |
| `bad_signature.json` | T5: valid claim, flipped signature byte |

## Keys

| File | Contents |
|---|---|
| `keys/toa-conformance-test-v1.json` | Public key (verify) |
| `keys/toa-conformance-test-v1.private.json` | **TEST ONLY** private key (sign fixtures) |

The private key is intentionally committed so anyone can regenerate or extend golden documents. **Never** use it in production.

Product / human home: [agentstatus.dev](https://agentstatus.dev). Wire extension id (SEP-2133 reverse-DNS): `dev.agentstatus/toa`.

## Fixture store URIs

Reference-mode validators may resolve:

```text
fixture:<stem>
```

Examples: `fixture:pass_functional`, `fixture:fail_functional`.

## Verify a document

```bash
cd python && pip install -e .
toa-verify ../mcp-extension/conformance/fixtures/pass_functional.json \
  --public-key ../mcp-extension/conformance/fixtures/keys/toa-conformance-test-v1.json \
  --require-emitter toa-conformance \
  --require-layer functional=pass
```
