"""Reference attach path: sign → binding → _meta → require enforcement."""

from __future__ import annotations

from pathlib import Path

from toa_ext import ClientSettings, EXTENSION_ID
from toa_ext.attach import (
    TOA_ERROR_CODE,
    attach_binding_to_result,
    attach_signed_document,
    build_claim,
    enforce_client_require,
    reference_binding,
    should_attach,
)
from toa_verify import verify_document
from toa_verify.sign import sign_document

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
        reasons=["attach-path-test"],
    )
    base.update(kwargs)
    return build_claim(**base)


def test_should_attach_policy():
    req = ClientSettings(require=True)
    assert should_attach(server_attach="on_require", client_settings=req) is True
    assert should_attach(server_attach="on_require", client_settings=ClientSettings()) is False
    assert should_attach(server_attach="always", client_settings=None) is True
    assert should_attach(server_attach="never", client_settings=req) is False


def test_attach_embedded_roundtrip():
    bare = {"content": [{"type": "text", "text": "hi"}], "isError": False}
    out = attach_signed_document(
        bare,
        claim=_claim(),
        private_key=PRIV,
        emitter_role="third_party",
        mode="embedded",
        public_key_id="test-v1",
    )
    binding = out["_meta"][EXTENSION_ID]
    assert binding["mode"] == "embedded"
    doc = binding["document"]
    assert verify_document(doc, public_key=PUB, require_emitter="toa-conformance")["valid"]

    enforced = enforce_client_require(
        out,
        client_settings=ClientSettings(require=True, require_emitter="toa-conformance"),
        public_key=PUB,
        expected_tool_name="echo",
    )
    assert enforced["ok"] is True


def test_enforce_require_missing_binding():
    enforced = enforce_client_require(
        {"content": [{"type": "text", "text": "hi"}]},
        client_settings=ClientSettings(require=True),
        public_key=PUB,
    )
    assert enforced["ok"] is False
    assert enforced["error"]["code"] == TOA_ERROR_CODE
    assert enforced["error"]["data"]["reason"] == "missing_binding"


def test_signed_negative_disposition_roundtrip():
    claim = _claim(disposition="failed", decision_id="d-neg")
    # force fail layers for realism
    claim["layers"] = {
        **PASS_LAYERS,
        "functional": "fail",
    }
    doc = sign_document(claim, private_key=PRIV, public_key_id="test-v1")
    assert doc["disposition"] == "failed"
    assert verify_document(doc, public_key=PUB, require_emitter="toa-conformance")["valid"]


def test_attach_reference_mode_with_store():
    doc = sign_document(_claim(decision_id="d-ref"), private_key=PRIV, public_key_id="test-v1")
    binding = reference_binding(
        uri="fixture:generated", document=doc, emitter_role="observer"
    )
    result = attach_binding_to_result({"content": []}, binding)
    enforced = enforce_client_require(
        result,
        client_settings=ClientSettings(
            require=True,
            accepted_emitter_roles=["observer"],
            require_emitter="toa-conformance",
        ),
        public_key=PUB,
        document_store={"fixture:generated": doc},
        expected_tool_name="echo",
    )
    assert enforced["ok"] is True, enforced
