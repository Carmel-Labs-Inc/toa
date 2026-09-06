"""Unit tests for AttestationBinding validation (T4–T8, T10 style)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from toa_ext import ClientSettings, validate_binding
from toa_ext.binding import load_conformance_public_key

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "mcp-extension" / "conformance" / "fixtures"
NOW = datetime(2026, 9, 6, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def public_key():
    return load_conformance_public_key(FIXTURES)


@pytest.fixture(scope="module")
def store():
    docs = {}
    for path in FIXTURES.glob("*.json"):
        docs[f"fixture:{path.stem}"] = json.loads(path.read_text())
    return docs


def _doc(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _embedded(doc_name: str, *, emitter_role: str = "third_party"):
    return {
        "mode": "embedded",
        "emitter_role": emitter_role,
        "spec": "toa/0.1",
        "document": _doc(doc_name),
    }


def _reference(
    doc_name: str,
    *,
    emitter_role: str = "third_party",
    payload_hash: str | None = None,
    emitter: dict | None = None,
):
    doc = _doc(doc_name)
    return {
        "mode": "reference",
        "emitter_role": emitter_role,
        "spec": "toa/0.1",
        "uri": f"fixture:{doc_name}",
        "payload_hash": payload_hash if payload_hash is not None else doc["payload_hash"],
        "emitter": emitter if emitter is not None else dict(doc["emitter"]),
    }


def _require_settings(**overrides) -> ClientSettings:
    base = dict(
        require=True,
        accepted_emitter_roles=["third_party", "observer"],
        require_emitter="toa-conformance",
        max_age_seconds=604800,
        min_layers={"reach": "pass", "invoke": "pass", "functional": "pass"},
    )
    base.update(overrides)
    return ClientSettings(**base)


def test_t2_style_pass_embedded(public_key, store):
    result = validate_binding(
        _embedded("pass_functional"),
        settings=_require_settings(),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is True
    assert result["layers"]["functional"] == "pass"


def test_t3_missing_binding_fails_closed(public_key):
    result = validate_binding(
        None,
        settings=_require_settings(),
        public_key=public_key,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "missing_binding"


def test_t3_missing_ok_when_not_required(public_key):
    result = validate_binding(
        None,
        settings=ClientSettings(require=False),
        public_key=public_key,
        now=NOW,
    )
    assert result["valid"] is True


def test_t4_role_pinning_rejects_server(public_key, store):
    result = validate_binding(
        _embedded("server_role", emitter_role="server"),
        settings=_require_settings(accepted_emitter_roles=["third_party"]),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "emitter_role"


def test_t5_signature_invalid(public_key, store):
    result = validate_binding(
        _embedded("bad_signature"),
        settings=_require_settings(),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "invalid_signature"


def test_t6_min_layers_functional(public_key, store):
    result = validate_binding(
        _embedded("fail_functional"),
        settings=_require_settings(),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "min_layers"
    assert result["layer"] == "functional"


def test_t7_max_age(public_key, store):
    result = validate_binding(
        _embedded("expired"),
        settings=_require_settings(max_age_seconds=604800),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "expired"


def test_t8_reference_hash_mismatch(public_key, store):
    binding = _reference(
        "pass_functional",
        payload_hash="sha256:" + ("0" * 64),
    )
    result = validate_binding(
        binding,
        settings=_require_settings(),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "hash_mismatch"


def test_t8_reference_hash_ok(public_key, store):
    result = validate_binding(
        _reference("pass_functional"),
        settings=_require_settings(),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is True
    assert result["mode"] == "reference"


def test_t10_require_emitter_name(public_key, store):
    result = validate_binding(
        _embedded("pass_functional"),
        settings=_require_settings(require_emitter="someone-else"),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "emitter_name"


def test_spec_mismatch_on_binding(public_key, store):
    binding = _embedded("pass_functional")
    binding["spec"] = "toa/9.9"
    result = validate_binding(
        binding,
        settings=_require_settings(),
        public_key=public_key,
        document_store=store,
        now=NOW,
    )
    assert result["valid"] is False
    assert result["reason"] == "spec_mismatch"


def test_fixture_uri_default_store(public_key):
    """Default fixture store resolves fixture:pass_functional from packaged path."""
    result = validate_binding(
        _reference("pass_functional"),
        settings=_require_settings(),
        public_key=public_key,
        now=NOW,
    )
    assert result["valid"] is True


def test_golden_documents_verify_with_toa_verify(public_key):
    from toa_verify import verify_document

    for name in (
        "pass_functional",
        "fail_functional",
        "expired",
        "wrong_tool",
        "server_role",
    ):
        doc = _doc(name)
        result = verify_document(doc, public_key=public_key, require_emitter="toa-conformance")
        assert result["valid"] is True, name

    bad = verify_document(_doc("bad_signature"), public_key=public_key)
    assert bad["valid"] is False
    assert bad["reason"] == "invalid_signature"
