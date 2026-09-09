"""Wire constants for the incubating TOA MCP extension."""

from __future__ import annotations

from pathlib import Path

# Reverse-DNS extension id (NOT the literal host agentstatus.dev/toa).
EXTENSION_ID = "dev.agentstatus/toa"

TOA_SPEC = "toa/0.1"

# Provisional JSON-RPC application error (see wire spec §10).
TOA_ERROR_CODE = -38100  # ToaAttestationFailure; see mcp-extension/DECISIONS.md

EMITTER_ROLES = frozenset({"third_party", "observer", "server"})
ATTACH_MODES = frozenset({"never", "on_require", "always"})
LAYER_OUTCOMES = frozenset({"pass", "warn", "fail", "n/a"})

DEFAULT_ACCEPTED_EMITTER_ROLES = ("third_party", "observer")
DEFAULT_MIN_LAYERS_WHEN_REQUIRE = {
    "reach": "pass",
    "invoke": "pass",
    "functional": "pass",
}
DEFAULT_MAX_AGE_SECONDS = 604800

CONFORMANCE_EMITTER_NAME = "toa-conformance"
CONFORMANCE_KEY_ID = "test-v1"

# Wall-clock independent "now" for golden fixtures dated 2026-09-01.
from datetime import datetime, timezone

FIXTURE_CLOCK = datetime(2026, 9, 1, 13, 0, 0, tzinfo=timezone.utc)

# conformance/ is the parent of harness/
HARNESS_ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE_ROOT = HARNESS_ROOT.parent
FIXTURES_ROOT = CONFORMANCE_ROOT / "fixtures"
KEYS_DIR = FIXTURES_ROOT / "keys"
DOCUMENTS_DIR = FIXTURES_ROOT / "documents"
