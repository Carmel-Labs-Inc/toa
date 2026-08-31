"""Round-trip and fixture tests for toa-verify."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from toa_verify import claim_for_signing, verify_document
from toa_verify.verify import canonical_json

ROOT = Path(__file__).resolve().parents[2]


def test_signed_example_verifies_with_bundled_key():
    doc = json.loads((ROOT / "examples" / "signed-example.json").read_text())
    result = verify_document(doc, require_emitter="agentstatus")
    assert result["valid"] is True
    assert result["layers"]["functional"] == "pass"


def test_unsigned_example_fails():
    doc = json.loads((ROOT / "examples" / "unsigned-example.json").read_text())
    result = verify_document(doc)
    assert result["valid"] is False
    assert result["reason"] == "missing_signature"


def test_tamper_breaks_signature():
    doc = json.loads((ROOT / "examples" / "signed-example.json").read_text())
    doc["layers"] = {**doc["layers"], "functional": "fail"}
    result = verify_document(doc)
    assert result["valid"] is False
    assert result["reason"] == "invalid_signature"


def test_local_keypair_roundtrip(tmp_path):
    priv = Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes_raw()
        if hasattr(priv.public_key(), "public_bytes_raw")
        else priv.public_key().public_bytes(
            encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"]).serialization.Encoding.Raw,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["serialization"]).serialization.PublicFormat.Raw,
        )
    ).decode()
    # cryptography Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization

    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode()

    claim = {
        "spec": "toa/0.1",
        "toa_id": "toa_" + ("a" * 20),
        "tool": {"name": "t", "server_id": "s", "catalog_hash": None},
        "run": {"decision_id": "d", "agent_id": "a"},
        "observed_at": "2026-01-01T00:00:00Z",
        "layers": {
            "reach": "pass",
            "invoke": "pass",
            "functional": "pass",
            "shape": "n/a",
            "openapi_fidelity": "n/a",
            "compositional": "n/a",
        },
        "outcome_grade": None,
        "business_outcome_ok": None,
        "reasons": [],
        "emitter": {"name": "demo", "version": "0", "key_id": "demo"},
    }
    body = claim_for_signing(claim)
    sig = base64.b64encode(priv.sign(canonical_json(body))).decode()
    doc = {**body, "signature": sig, "public_key_id": "demo"}
    keyfile = tmp_path / "k.json"
    keyfile.write_text(json.dumps({"public_key": pub_b64}))
    assert verify_document(doc, public_key=keyfile, require_emitter="demo")["valid"] is True


def test_max_age_rejects_stale():
    from datetime import datetime, timezone

    doc = json.loads((ROOT / "examples" / "signed-example.json").read_text())
    # observed_at in fixture is in the past relative to a far-future now
    result = verify_document(
        doc,
        require_emitter="agentstatus",
        max_age_seconds=60,
        now=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    assert result["valid"] is False
    assert result["reason"] == "stale_attestation"


def test_max_age_accepts_fresh():
    from datetime import datetime, timezone

    doc = json.loads((ROOT / "examples" / "signed-example.json").read_text())
    observed = doc["observed_at"]
    # parse fixture time and set now just after it
    from toa_verify.verify import parse_observed_at

    obs = parse_observed_at(observed)
    result = verify_document(
        doc,
        require_emitter="agentstatus",
        max_age_seconds=86400 * 365 * 50,
        now=obs,
    )
    assert result["valid"] is True


def test_parse_max_age_seconds():
    from toa_verify.verify import parse_max_age_seconds

    assert parse_max_age_seconds("24h") == 86400
    assert parse_max_age_seconds("7d") == 604800
    assert parse_max_age_seconds("90m") == 5400
    assert parse_max_age_seconds(3600) == 3600
