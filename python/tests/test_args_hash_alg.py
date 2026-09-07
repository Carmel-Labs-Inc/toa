"""args_hash commitment + algorithm-agnostic envelope defaults."""

from __future__ import annotations

from pathlib import Path

from toa_verify import args_hash_for, sign_document, verify_document
from toa_verify.verify import DEFAULT_ALG, resolve_alg
from toa_ext import ClientSettings, validate_binding
from toa_ext.attach import build_claim, embedded_binding

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_KEYS = ROOT / "mcp-extension" / "conformance" / "fixtures" / "keys"
PRIV = FIXTURE_KEYS / "toa-conformance-test-v1.private.json"
PUB = FIXTURE_KEYS / "toa-conformance-test-v1.json"

PASS_LAYERS = {
    "reach": "pass",
    "invoke": "pass",
    "functional": "pass",
    "shape": "n/a",
    "openapi_fidelity": "n/a",
    "compositional": "n/a",
}


def _claim(**kwargs):
    base = dict(
        tool_name="echo",
        server_id="ref-server",
        decision_id="d1",
        agent_id="a1",
        layers=PASS_LAYERS,
        emitter_name="toa-conformance",
        emitter_key_id="test-v1",
        reasons=["args-hash-test"],
    )
    base.update(kwargs)
    return build_claim(**base)


def test_args_hash_roundtrip_and_match():
    args = {"text": "hello", "n": 1}
    digest = args_hash_for(args)
    assert digest.startswith("sha256:")
    doc = sign_document(
        _claim(args_hash=digest, decision_id="d-args"),
        private_key=PRIV,
        public_key_id="test-v1",
    )
    assert doc["args_hash"] == digest
    assert doc["alg"] == DEFAULT_ALG
    ok = verify_document(
        doc,
        public_key=PUB,
        require_emitter="toa-conformance",
        expected_args_hash=digest,
    )
    assert ok["valid"] is True, ok


def test_require_args_hash_fails_when_absent():
    doc = sign_document(_claim(decision_id="d-no-args"), private_key=PRIV, public_key_id="test-v1")
    assert "args_hash" not in doc
    bad = verify_document(doc, public_key=PUB, require_args_hash=True)
    assert bad["valid"] is False
    assert bad["reason"] == "missing_args_hash"


def test_args_hash_mismatch():
    digest = args_hash_for({"text": "a"})
    doc = sign_document(
        _claim(args_hash=digest, decision_id="d-mis"),
        private_key=PRIV,
        public_key_id="test-v1",
    )
    bad = verify_document(
        doc,
        public_key=PUB,
        expected_args_hash=args_hash_for({"text": "b"}),
    )
    assert bad["valid"] is False
    assert bad["reason"] == "args_hash_mismatch"


def test_legacy_doc_without_alg_still_verifies():
    """Absent alg must default to Ed25519 (non-breaking)."""
    doc = sign_document(_claim(decision_id="d-alg"), private_key=PRIV, public_key_id="test-v1")
    assert doc["alg"] == "Ed25519"
    legacy = {k: v for k, v in doc.items() if k != "alg"}
    assert resolve_alg(legacy) == "Ed25519"
    assert verify_document(legacy, public_key=PUB, require_emitter="toa-conformance")["valid"]


def test_unsupported_algorithm_fails_closed():
    doc = sign_document(_claim(decision_id="d-pq"), private_key=PRIV, public_key_id="test-v1")
    doc["alg"] = "ML-DSA-65"
    bad = verify_document(doc, public_key=PUB)
    assert bad["valid"] is False
    assert bad["reason"].startswith("unsupported_algorithm")


def test_binding_require_args_hash():
    digest = args_hash_for({"x": 1})
    doc = sign_document(
        _claim(args_hash=digest, decision_id="d-bind"),
        private_key=PRIV,
        public_key_id="test-v1",
    )
    binding = embedded_binding(doc, emitter_role="third_party")
    ok = validate_binding(
        binding,
        settings=ClientSettings(
            require=True,
            require_emitter="toa-conformance",
            require_args_hash=True,
            expected_args_hash=digest,
        ),
        public_key=PUB,
        expected_tool_name="echo",
    )
    assert ok["valid"] is True, ok

    missing = validate_binding(
        embedded_binding(
            sign_document(_claim(decision_id="d-bind2"), private_key=PRIV, public_key_id="test-v1"),
            emitter_role="third_party",
        ),
        settings=ClientSettings(require=True, require_args_hash=True),
        public_key=PUB,
        expected_tool_name="echo",
    )
    assert missing["valid"] is False
    assert missing["reason"] == "args_hash"
