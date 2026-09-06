# TOA MCP extension conformance harness

In-process reference harness for `dev.agentstatus/toa` scenarios **T1–T10**
(see [`../SCENARIOS.md`](../SCENARIOS.md)).

No network MCP servers. A fake client/server pair advertises capabilities and
returns `tools/call` results with or without `_meta["dev.agentstatus/toa"]`.

## Layout

```text
conformance/
  SCENARIOS.md
  fixtures/                 # golden keys + documents (toa_ext workstream)
  harness/
    toa_ext_conformance/    # this package
    tests/
    README.md
    pyproject.toml
```

## Validate library seam

`toa_ext_conformance.validate_api.validate_binding()`:

1. Prefers `toa_ext.validate_binding` (`toa/python/toa_ext`) when importable.
2. Falls back to a local §8 stub + optional `toa_verify` for Ed25519.

Crypto scenarios SKIP with `fixtures_missing:…` if goldens/keys are absent, or
`crypto_unavailable` if neither `toa_ext` nor `toa_verify` can verify signatures.

## Run

```bash
cd mcp-extension/conformance/harness

# Put toa_ext + toa_verify on PYTHONPATH (from repo python/)
export PYTHONPATH=".:../../../python"

pip install -e ".[dev]"          # harness
pip install -e "../../../python" # toa_verify + toa_ext (cryptography)

python -m pytest
python -m toa_ext_conformance
python -m toa_ext_conformance --only T1 T3 T9
python -m toa_ext_conformance --json
python -m toa_ext_conformance --fixtures
```

Without editable install:

```bash
PYTHONPATH=.:../../../python python -m pytest
PYTHONPATH=.:../../../python python -m toa_ext_conformance
```

## Status with current fixtures + `toa_ext`

| Scenario | Status |
|---|---|
| T1–T10 | PASS |

Without fixtures/keys: T1, T3, T9 PASS; T2, T4–T8, T10 SKIP.

Exit code is non-zero only on **FAIL**. SKIP does not fail the CLI.
