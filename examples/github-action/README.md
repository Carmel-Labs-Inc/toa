# CI example: verify a TOA artifact

Place a signed `toa.json` in your repo (from AgentStatus emit API) or download it in an earlier job step.

```yaml
name: verify-toa
on:
  pull_request:
  workflow_dispatch:
    inputs:
      toa_path:
        description: Path to signed TOA JSON
        default: toa.json

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install toa-verify
        run: |
          pip install "cryptography>=42"
          pip install -e "${{ github.workspace }}/python"
        # When consuming from this repo as a checkout of Carmel-Labs-Inc/toa:
        #   git clone https://github.com/Carmel-Labs-Inc/toa.git
        # Or vendor keys/ + python/toa_verify into your repo.

      - name: Verify attestation
        run: |
          python -m toa_verify "${{ inputs.toa_path || 'toa.json' }}" \
            --public-key keys/agentstatus-v1.json \
            --require-emitter agentstatus \
            --require-layer functional=pass \
            --max-age 7d
```

## Against AgentStatus HTTP verify

If you prefer not to vendor keys:

```bash
curl -sS -X POST https://api.agentstatus.dev/api/rora/public/toa/verify \
  -H 'content-type: application/json' \
  -d @"toa-body.json"
```

Where `toa-body.json` is `{ "document": { ...signed TOA... } }`.
