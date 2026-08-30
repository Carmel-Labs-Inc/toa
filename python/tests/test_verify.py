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
