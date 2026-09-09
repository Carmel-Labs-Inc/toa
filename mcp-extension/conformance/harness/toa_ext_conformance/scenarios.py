"""T1–T18 scenario implementations (in-process fake MCP)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping, Optional

from .constants import CONFORMANCE_EMITTER_NAME, EXTENSION_ID, FIXTURE_CLOCK
from .fake_mcp import FakeMcpClient, FakeMcpServer
from .fixtures import missing_fixture_reason, try_load_document, try_load_key
from .types import ClientToaSettings, ScenarioResult, ServerToaSettings, Status
from .validate_api import parse_server_toa_settings, validate_binding


def _pass(
    scenario_id: str,
    name: str,
    reason: str = "ok",
    *,
    checks: Optional[Dict[str, str]] = None,
) -> ScenarioResult:
    return ScenarioResult(scenario_id, name, Status.PASS, reason, checks=checks or {})


def _fail(
    scenario_id: str,
    name: str,
    reason: str,
    detail: Optional[str] = None,
    *,
    checks: Optional[Dict[str, str]] = None,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id, name, Status.FAIL, reason, detail=detail, checks=checks or {}
    )


def _skip(scenario_id: str, name: str, reason: str, detail: Optional[str] = None) -> ScenarioResult:
    return ScenarioResult(scenario_id, name, Status.SKIP, reason, detail=detail)


def _embedded_binding(document: Mapping[str, Any], emitter_role: str = "third_party") -> Dict[str, Any]:
    return {
        "mode": "embedded",
        "emitter_role": emitter_role,
        "spec": "toa/0.1",
        "document": deepcopy(dict(document)),
    }


def _reference_binding(
    document: Mapping[str, Any],
    *,
    uri: str,
    payload_hash: Optional[str] = None,
    emitter_role: str = "third_party",
) -> Dict[str, Any]:
    emitter = document.get("emitter") if isinstance(document.get("emitter"), Mapping) else {}
    return {
        "mode": "reference",
        "emitter_role": emitter_role,
        "spec": "toa/0.1",
        "uri": uri,
        "payload_hash": payload_hash if payload_hash is not None else document.get("payload_hash"),
        "emitter": {
            "name": emitter.get("name"),
            "version": emitter.get("version", "0.1.0"),
            "key_id": emitter.get("key_id", "test-v1"),
        },
    }


def _public_key_material() -> Any:
    return try_load_key()


def _crypto_blocked(validation_reason: str) -> bool:
    return validation_reason in {"crypto_unavailable", "no_public_key_configured"}


def scenario_t1_advertisement() -> ScenarioResult:
    """T1 — server advertises correct extension id + settings shape."""
    sid, name = "T1", "toa-capability-advertisement"
    checks: Dict[str, str] = {}

    good = FakeMcpServer(toa=ServerToaSettings(attach="on_require"), advertise_toa=True)
    caps = good.initialize_result()["capabilities"]
    extensions = caps.get("extensions") or {}
    if EXTENSION_ID not in extensions:
        return _fail(sid, name, "missing_extension_id", checks={"ext_key": "FAIL"})
    checks["ext_key"] = "PASS"

    ok, reason, _norm = parse_server_toa_settings(extensions[EXTENSION_ID])
    if not ok:
        return _fail(sid, name, reason, checks={**checks, "settings": "FAIL"})
    # Unknown fields ignored
    messy = dict(extensions[EXTENSION_ID])
    messy["futureField"] = {"nested": True}
    ok2, reason2, _ = parse_server_toa_settings(messy)
    if not ok2:
        return _fail(sid, name, reason2, detail="unknown_fields_must_be_ignored", checks={**checks, "settings": "FAIL"})
    checks["settings"] = "PASS"

    # Invalid enum rejected
    bad_attach = FakeMcpServer(toa=ServerToaSettings(attach="on_require"))
    bad_caps = bad_attach.initialize_result()["capabilities"]["extensions"][EXTENSION_ID]
    bad_caps = dict(bad_caps)
    bad_caps["attach"] = "sometimes"
    ok3, reason3, _ = parse_server_toa_settings(bad_caps)
    if ok3 or "invalid_attach" not in reason3:
        return _fail(sid, name, "invalid_attach_not_rejected", checks={**checks, "enum": "FAIL"})
    checks["enum"] = "PASS"

    # MUST NOT advertise under capabilities.toa
    wrong = FakeMcpServer(wrong_key_toa=True, advertise_toa=False)
    wrong_caps = wrong.initialize_result()["capabilities"]
    if "toa" in wrong_caps and EXTENSION_ID not in (wrong_caps.get("extensions") or {}):
        # Harness detects the anti-pattern: a conforming server must not do this.
        checks["wrong_key_detected"] = "PASS"
    else:
        return _fail(sid, name, "wrong_key_not_detected", checks={**checks, "wrong_key_detected": "FAIL"})

    # Conforming server: extensions id present, top-level toa absent
    if "toa" in caps:
        return _fail(sid, name, "advertised_under_capabilities.toa", checks={**checks, "no_wrong_key": "FAIL"})
    checks["no_wrong_key"] = "PASS"

    return _pass(sid, name, checks=checks)


def scenario_t2_attach_on_require() -> ScenarioResult:
    sid, name = "T2", "toa-attach-on-require"
    miss = missing_fixture_reason("pass_functional", need_key=True)
    if miss:
        return _skip(sid, name, miss)

    doc = try_load_document("pass_functional")
    assert doc is not None
    key = _public_key_material()

    def factory(tool: str, _args: Mapping[str, Any], _client: ClientToaSettings) -> Optional[Dict[str, Any]]:
        if tool != "echo":
            return None
        return _embedded_binding(doc, emitter_role="third_party")

    server = FakeMcpServer(
        toa=ServerToaSettings(attach="on_require", supported_emitter_roles=["third_party"]),
        binding_factory=factory,
    )
    client = FakeMcpClient(
        toa=ClientToaSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter=CONFORMANCE_EMITTER_NAME,
        )
    )
    client.connect(server)
    # evaluate with explicit key via validate path
    raw = server.call_tool("echo", {"text": "hi"})
    binding = (raw._meta or {}).get(EXTENSION_ID)
    if binding is None:
        return _fail(sid, name, "missing_binding", detail="server did not attach")

    vr = validate_binding(
        binding,
        client_settings=client.toa,
        tool_name="echo",
        public_key=key,
        now=FIXTURE_CLOCK,
    )
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if not vr.valid:
        return _fail(
            sid,
            name,
            vr.reason,
            detail=vr.detail,
            checks={"binding": "present", "validate": "FAIL"},
        )
    return _pass(sid, name, checks={"binding": "PASS", "validate": "PASS", "tool": "PASS"})


def scenario_t3_require_missing_fails_closed() -> ScenarioResult:
    sid, name = "T3", "toa-require-missing-fails-closed"
    server = FakeMcpServer(
        toa=ServerToaSettings(attach="never"),
        advertise_toa=True,
        force_no_binding=True,
    )
    client = FakeMcpClient(toa=ClientToaSettings(require=True, accepted_emitter_roles=["third_party"]))
    client.connect(server)
    outcome = client.call_tool(server, "echo", {"text": "x"})

    # Core RPC may succeed
    rpc = outcome["rpc"]
    if rpc.get("isError"):
        return _fail(sid, name, "rpc_failed", detail="core call should succeed")

    if outcome.get("toa_ok") is True:
        return _fail(sid, name, "accepted_without_binding", detail="client must fail-closed")
    if outcome.get("toa_reason") != "missing_binding":
        return _fail(
            sid,
            name,
            "wrong_reason",
            detail=f"expected missing_binding got {outcome.get('toa_reason')}",
        )
    return _pass(sid, name, checks={"rpc": "PASS", "fail_closed": "PASS", "reason": "missing_binding"})


def scenario_t4_role_pinning_rejects_server() -> ScenarioResult:
    sid, name = "T4", "toa-role-pinning-rejects-server"
    miss = missing_fixture_reason("server_role", need_key=True)
    if miss:
        return _skip(sid, name, miss)

    doc = try_load_document("server_role")
    assert doc is not None
    key = _public_key_material()

    def factory(tool: str, _args: Mapping[str, Any], _client: ClientToaSettings) -> Optional[Dict[str, Any]]:
        return _embedded_binding(doc, emitter_role="server")

    server = FakeMcpServer(toa=ServerToaSettings(attach="always"), binding_factory=factory)
    client = FakeMcpClient(
        toa=ClientToaSettings(require=True, accepted_emitter_roles=["third_party"])
    )
    client.connect(server)
    raw = server.call_tool("echo", {"text": "x"})
    binding = raw._meta.get(EXTENSION_ID)
    vr = validate_binding(binding, client_settings=client.toa, tool_name="echo", public_key=key, now=FIXTURE_CLOCK)
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if vr.valid:
        return _fail(sid, name, "accepted_server_role", detail="server role must be rejected")
    if vr.reason != "emitter_role":
        return _fail(sid, name, "wrong_reason", detail=f"expected emitter_role got {vr.reason}")
    return _pass(sid, name, checks={"reject": "PASS", "reason": "emitter_role"})


def scenario_t5_signature_invalid() -> ScenarioResult:
    sid, name = "T5", "toa-signature-invalid"
    miss = missing_fixture_reason("bad_signature", need_key=True)
    if miss:
        return _skip(sid, name, miss)

    doc = try_load_document("bad_signature")
    assert doc is not None
    key = _public_key_material()
    binding = _embedded_binding(doc, emitter_role="third_party")
    settings = ClientToaSettings(require=True, accepted_emitter_roles=["third_party"])
    vr = validate_binding(binding, client_settings=settings, tool_name="echo", public_key=key, now=FIXTURE_CLOCK)
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if vr.valid or vr.reason != "invalid_signature":
        return _fail(sid, name, "wrong_reason", detail=f"expected invalid_signature got {vr.reason}")
    return _pass(sid, name, checks={"reason": "invalid_signature"})


def scenario_t6_min_layers_functional() -> ScenarioResult:
    sid, name = "T6", "toa-min-layers-functional"
    miss = missing_fixture_reason("fail_functional", need_key=True)
    if miss:
        return _skip(sid, name, miss)

    doc = try_load_document("fail_functional")
    assert doc is not None
    key = _public_key_material()
    binding = _embedded_binding(doc, emitter_role="third_party")
    settings = ClientToaSettings(
        require=True,
        accepted_emitter_roles=["third_party"],
        min_layers={"reach": "pass", "invoke": "pass", "functional": "pass"},
    )
    vr = validate_binding(binding, client_settings=settings, tool_name="echo", public_key=key, now=FIXTURE_CLOCK)
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if vr.valid or vr.reason != "min_layers":
        return _fail(sid, name, "wrong_reason", detail=f"expected min_layers got {vr.reason}")
    return _pass(sid, name, checks={"reason": "min_layers"})


def scenario_t7_max_age() -> ScenarioResult:
    sid, name = "T7", "toa-max-age"
    miss = missing_fixture_reason("expired", need_key=True)
    if miss:
        return _skip(sid, name, miss)

    doc = try_load_document("expired")
    assert doc is not None
    key = _public_key_material()
    binding = _embedded_binding(doc, emitter_role="third_party")
    settings = ClientToaSettings(
        require=True,
        accepted_emitter_roles=["third_party"],
        max_age_seconds=3600,
    )
    vr = validate_binding(binding, client_settings=settings, tool_name="echo", public_key=key, now=FIXTURE_CLOCK)
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if vr.valid or vr.reason != "expired":
        return _fail(sid, name, "wrong_reason", detail=f"expected expired got {vr.reason}")
    return _pass(sid, name, checks={"reason": "expired"})


def scenario_t8_reference_hash_mismatch() -> ScenarioResult:
    sid, name = "T8", "toa-reference-hash-mismatch"
    miss = missing_fixture_reason("pass_functional", need_key=True)
    if miss:
        return _skip(sid, name, miss)

    doc = try_load_document("pass_functional")
    assert doc is not None
    key = _public_key_material()
    uri = "fixture:pass_functional"
    binding = _reference_binding(
        doc,
        uri=uri,
        payload_hash="sha256:" + ("0" * 64),
        emitter_role="third_party",
    )
    settings = ClientToaSettings(require=True, accepted_emitter_roles=["third_party"])
    from .fixtures import default_document_store

    vr = validate_binding(
        binding,
        client_settings=settings,
        tool_name="echo",
        public_key=key,
        document_store=default_document_store(),
        now=FIXTURE_CLOCK,
    )
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if vr.valid or vr.reason != "hash_mismatch":
        return _fail(sid, name, "wrong_reason", detail=f"expected hash_mismatch got {vr.reason}")
    return _pass(sid, name, checks={"reason": "hash_mismatch"})


def scenario_t9_graceful_degradation() -> ScenarioResult:
    sid, name = "T9", "toa-graceful-degradation"

    # Client does not advertise TOA; server may attach — core must still succeed.
    def factory(tool: str, _args: Mapping[str, Any], _client: ClientToaSettings) -> Optional[Dict[str, Any]]:
        # Attach a structural stub binding; client without TOA ignores _meta.
        return {
            "mode": "embedded",
            "emitter_role": "third_party",
            "spec": "toa/0.1",
            "document": {"spec": "toa/0.1", "tool": {"name": tool}},
        }

    server = FakeMcpServer(
        toa=ServerToaSettings(attach="always"),
        binding_factory=factory,
    )
    client = FakeMcpClient(advertise_toa=False, toa=None)
    client.connect(server)
    outcome = client.call_tool(server, "echo", {"text": "hello"})
    rpc = outcome["rpc"]
    if rpc.get("isError"):
        return _fail(sid, name, "rpc_failed")
    content = rpc.get("content") or []
    if not content or content[0].get("text") != "hello":
        return _fail(sid, name, "echo_mismatch", detail=str(content))
    if outcome.get("toa_reason") != "not_required":
        return _fail(sid, name, "unexpected_toa_error", detail=str(outcome.get("toa_reason")))
    # Binding may be present in _meta; must not introduce TOA error codes
    if outcome.get("toa_ok") is False:
        return _fail(sid, name, "toa_error_without_require")
    return _pass(sid, name, checks={"echo": "PASS", "no_toa_error": "PASS"})


def scenario_t10_require_emitter_name() -> ScenarioResult:
    sid, name = "T10", "toa-require-emitter-name"
    miss = missing_fixture_reason("pass_functional", need_key=True)
    if miss:
        return _skip(sid, name, miss)

    key = _public_key_material()
    other = try_load_document("other_emitter")
    if other is not None:
        binding = _embedded_binding(other, emitter_role="third_party")
        settings = ClientToaSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter=CONFORMANCE_EMITTER_NAME,
        )
        tool = "echo"
        expected_detail = "other_emitter fixture"
    else:
        # No alternate-emitter golden yet: prove requireEmitter pin by requiring a
        # name that does not match pass_functional's emitter (toa-conformance).
        doc = try_load_document("pass_functional")
        assert doc is not None
        binding = _embedded_binding(doc, emitter_role="third_party")
        settings = ClientToaSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter="not-toa-conformance",
        )
        tool = "echo"
        expected_detail = "inverted_requireEmitter_until_other_emitter_fixture"

    vr = validate_binding(binding, client_settings=settings, tool_name=tool, public_key=key, now=FIXTURE_CLOCK)
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if vr.valid or vr.reason != "emitter_name":
        return _fail(sid, name, "wrong_reason", detail=f"expected emitter_name got {vr.reason}")
    return _pass(sid, name, checks={"reason": "emitter_name", "mode": expected_detail})


def scenario_t11_negotiation_record() -> ScenarioResult:
    """T11 — client persists NegotiationRecord at discover."""
    sid, name = "T11", "toa-negotiation-record"
    from toa_ext.negotiation import (
        NEGOTIATION_SPEC,
        validate_negotiation_record,
    )

    # Advertised
    server_yes = FakeMcpServer(toa=ServerToaSettings(attach="on_require"), advertise_toa=True)
    client_yes = FakeMcpClient(
        toa=ClientToaSettings(require=True, accepted_emitter_roles=["third_party"]),
        server_id="srv-yes",
    )
    client_yes.connect(server_yes)
    rec_yes = client_yes.negotiation_record
    if rec_yes is None:
        return _fail(sid, name, "missing_record_advertised")
    shape = validate_negotiation_record(rec_yes)
    if not shape.get("valid"):
        return _fail(sid, name, "schema_invalid", detail=str(shape))
    if rec_yes.get("spec") != NEGOTIATION_SPEC:
        return _fail(sid, name, "spec_mismatch")
    if rec_yes.get("server_advertised_toa") is not True:
        return _fail(sid, name, "expected_advertised_true")
    if not isinstance(rec_yes.get("server_settings"), dict):
        return _fail(sid, name, "missing_server_settings_copy")
    if rec_yes["server_settings"].get("attach") != "on_require":
        return _fail(sid, name, "settings_copy_wrong")

    # Not advertised
    server_no = FakeMcpServer(advertise_toa=False)
    client_no = FakeMcpClient(
        toa=ClientToaSettings(require=False),
        advertise_toa=False,
        server_id="srv-no",
    )
    # Still record even when client does not advertise TOA.
    init = server_no.initialize_result()
    from toa_ext.negotiation import negotiation_from_initialize

    rec_no = negotiation_from_initialize(init, server_id="srv-no")
    shape_no = validate_negotiation_record(rec_no)
    if not shape_no.get("valid"):
        return _fail(sid, name, "schema_invalid_no", detail=str(shape_no))
    if rec_no.get("server_advertised_toa") is not False:
        return _fail(sid, name, "expected_advertised_false")

    return _pass(
        sid,
        name,
        checks={"advertised": "PASS", "never": "PASS", "schema": "PASS"},
    )


def scenario_t12_signed_negative_disposition() -> ScenarioResult:
    """T12 — failure paths emit signed disposition, not silence."""
    sid, name = "T12", "toa-signed-negative-disposition"
    from pathlib import Path

    from toa_ext.attach import build_claim, embedded_binding
    from toa_ext.negotiation import (
        ABSENCE_ATTESTATION_GAP,
        ABSENCE_NEGATIVE,
        classify_absence,
        negotiation_from_initialize,
    )
    from toa_verify.sign import sign_document
    from toa_verify.verify import verify_document

    priv_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "keys"
        / "toa-conformance-test-v1.private.json"
    )
    if not priv_path.is_file():
        return _skip(sid, name, "missing_private_key", detail=str(priv_path))
    key = _public_key_material()
    if key is None:
        return _skip(sid, name, "missing_public_key")

    fail_layers = {
        "reach": "pass",
        "invoke": "pass",
        "functional": "fail",
        "shape": "n/a",
        "openapi_fidelity": "n/a",
        "compositional": "n/a",
    }

    def factory(tool: str, _args: Mapping[str, Any], _client: ClientToaSettings) -> Optional[Dict[str, Any]]:
        claim = build_claim(
            tool_name=tool,
            server_id="toa-conformance-fake",
            decision_id=f"neg-{tool}",
            agent_id="00000000-0000-0000-0000-0000000000c1",
            layers=fail_layers,
            emitter_name=CONFORMANCE_EMITTER_NAME,
            emitter_key_id="test-v1",
            reasons=["t12-signed-negative"],
            disposition="failed",
        )
        doc = sign_document(claim, private_key=priv_path, public_key_id="test-v1")
        return embedded_binding(doc, emitter_role="third_party")

    server = FakeMcpServer(
        toa=ServerToaSettings(attach="on_require", supported_emitter_roles=["third_party"]),
        binding_factory=factory,
    )
    client = FakeMcpClient(
        toa=ClientToaSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter=CONFORMANCE_EMITTER_NAME,
            # Negative evidence: do not require functional=pass for this check.
            min_layers={"reach": "pass", "invoke": "pass"},
        ),
        server_id="toa-conformance-fake",
    )
    init = client.connect(server)
    raw = server.call_tool("soft_fail", {})
    binding = (raw._meta or {}).get(EXTENSION_ID)
    if binding is None:
        return _fail(sid, name, "missing_binding", detail="silence on negative path")

    doc = binding.get("document")
    if not isinstance(doc, Mapping):
        return _fail(sid, name, "missing_document")
    if doc.get("disposition") not in ("failed", "refused", "unavailable"):
        return _fail(sid, name, "missing_negative_disposition", detail=str(doc.get("disposition")))

    vr = verify_document(doc, public_key=key, require_emitter=CONFORMANCE_EMITTER_NAME)
    if not vr.get("valid"):
        return _fail(sid, name, "verify_failed", detail=str(vr))

    # Crypto+role binding validate (min_layers allow fail on functional)
    pol = validate_binding(
        binding,
        client_settings=client.toa,
        tool_name="soft_fail",
        public_key=key,
        now=FIXTURE_CLOCK,
    )
    if _crypto_blocked(pol.reason):
        return _skip(sid, name, pol.reason, detail=pol.detail)
    if not pol.valid:
        return _fail(sid, name, pol.reason, detail=pol.detail)

    neg = classify_absence(
        negotiation=client.negotiation_record or negotiation_from_initialize(init, server_id="toa-conformance-fake"),
        attestation_present=True,
        document=doc,
        attach_expected=True,
    )
    if neg.get("class") != ABSENCE_NEGATIVE:
        return _fail(sid, name, "not_negative_evidence", detail=str(neg))
    if neg.get("class") == ABSENCE_ATTESTATION_GAP:
        return _fail(sid, name, "classified_as_gap")

    return _pass(
        sid,
        name,
        checks={"binding": "PASS", "disposition": "PASS", "verify": "PASS", "class": ABSENCE_NEGATIVE},
    )


def scenario_t13_absence_vs_never_advertised() -> ScenarioResult:
    """T13 — outside_toa ≠ attestation_gap."""
    sid, name = "T13", "toa-absence-vs-never-advertised"
    from toa_ext.negotiation import (
        ABSENCE_ATTESTATION_GAP,
        ABSENCE_OUTSIDE_TOA,
        classify_absence,
        negotiation_from_initialize,
    )

    never = FakeMcpServer(advertise_toa=False)
    init_never = never.initialize_result()
    rec_never = negotiation_from_initialize(init_never, server_id="srv-never")
    class_never = classify_absence(
        negotiation=rec_never,
        attestation_present=False,
        document=None,
        attach_expected=True,
    )
    if class_never.get("class") != ABSENCE_OUTSIDE_TOA:
        return _fail(sid, name, "expected_outside_toa", detail=str(class_never))

    advertised = FakeMcpServer(
        toa=ServerToaSettings(attach="on_require"),
        advertise_toa=True,
        force_no_binding=True,
    )
    client = FakeMcpClient(
        toa=ClientToaSettings(require=True, accepted_emitter_roles=["third_party"]),
        server_id="srv-gap",
    )
    client.connect(advertised)
    # Required call with no binding → gap
    class_gap = classify_absence(
        negotiation=client.negotiation_record,  # type: ignore[arg-type]
        attestation_present=False,
        document=None,
        attach_expected=True,
    )
    if class_gap.get("class") != ABSENCE_ATTESTATION_GAP:
        return _fail(sid, name, "expected_attestation_gap", detail=str(class_gap))

    if class_never["class"] == class_gap["class"]:
        return _fail(sid, name, "classes_collapsed")

    return _pass(
        sid,
        name,
        checks={
            "outside_toa": "PASS",
            "attestation_gap": "PASS",
            "distinct": "PASS",
        },
    )


def scenario_t14_optional_args_hash() -> ScenarioResult:
    """T14 — optional args_hash present and matches when verified against call args."""
    sid, name = "T14", "toa-optional-args-hash"
    from pathlib import Path

    from toa_ext.attach import build_claim, embedded_binding
    from toa_verify import args_hash_for, sign_document

    priv_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "keys"
        / "toa-conformance-test-v1.private.json"
    )
    if not priv_path.is_file():
        return _skip(sid, name, "missing_private_key", detail=str(priv_path))
    key = _public_key_material()
    if key is None:
        return _skip(sid, name, "missing_public_key")

    call_args = {"text": "hello-t14"}
    digest = args_hash_for(call_args)

    def factory(tool: str, args: Mapping[str, Any], _client: ClientToaSettings) -> Optional[Dict[str, Any]]:
        claim = build_claim(
            tool_name=tool,
            server_id="toa-conformance-fake",
            decision_id=f"args-{tool}",
            agent_id="00000000-0000-0000-0000-0000000000c1",
            layers={
                "reach": "pass",
                "invoke": "pass",
                "functional": "pass",
                "shape": "n/a",
                "openapi_fidelity": "n/a",
                "compositional": "n/a",
            },
            emitter_name=CONFORMANCE_EMITTER_NAME,
            emitter_key_id="test-v1",
            reasons=["t14-args-hash"],
            disposition="delivered",
            args_hash=args_hash_for(dict(args)),
        )
        doc = sign_document(claim, private_key=priv_path, public_key_id="test-v1")
        return embedded_binding(doc, emitter_role="third_party")

    server = FakeMcpServer(
        toa=ServerToaSettings(attach="on_require"),
        binding_factory=factory,
    )
    client = FakeMcpClient(
        toa=ClientToaSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter=CONFORMANCE_EMITTER_NAME,
            require_args_hash=False,
            expected_args_hash=digest,
        )
    )
    client.connect(server)
    raw = server.call_tool("echo", call_args)
    binding = (raw._meta or {}).get(EXTENSION_ID)
    if binding is None:
        return _fail(sid, name, "missing_binding")
    doc = binding.get("document") if isinstance(binding, Mapping) else None
    if not isinstance(doc, Mapping) or doc.get("args_hash") != digest:
        return _fail(sid, name, "args_hash_missing_or_wrong", detail=str((doc or {}).get("args_hash")))

    vr = validate_binding(
        binding,
        client_settings=client.toa,
        tool_name="echo",
        public_key=key,
        now=FIXTURE_CLOCK,
    )
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if not vr.valid:
        return _fail(sid, name, vr.reason, detail=vr.detail)
    return _pass(sid, name, checks={"args_hash": "PASS", "validate": "PASS"})


def scenario_t15_require_args_hash() -> ScenarioResult:
    """T15 — requireArgsHash fails closed when args_hash absent; passes when present."""
    sid, name = "T15", "toa-require-args-hash"
    from pathlib import Path

    from toa_ext.attach import build_claim, embedded_binding
    from toa_verify import args_hash_for, sign_document

    priv_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "keys"
        / "toa-conformance-test-v1.private.json"
    )
    if not priv_path.is_file():
        return _skip(sid, name, "missing_private_key", detail=str(priv_path))
    key = _public_key_material()
    if key is None:
        return _skip(sid, name, "missing_public_key")

    layers = {
        "reach": "pass",
        "invoke": "pass",
        "functional": "pass",
        "shape": "n/a",
        "openapi_fidelity": "n/a",
        "compositional": "n/a",
    }
    settings = ClientToaSettings(
        require=True,
        accepted_emitter_roles=["third_party"],
        require_emitter=CONFORMANCE_EMITTER_NAME,
        require_args_hash=True,
    )

    # Missing args_hash → fail
    claim_missing = build_claim(
        tool_name="echo",
        server_id="toa-conformance-fake",
        decision_id="t15-missing",
        agent_id="00000000-0000-0000-0000-0000000000c1",
        layers=layers,
        emitter_name=CONFORMANCE_EMITTER_NAME,
        emitter_key_id="test-v1",
        reasons=["t15-missing"],
        disposition="delivered",
    )
    doc_missing = sign_document(claim_missing, private_key=priv_path, public_key_id="test-v1")
    vr_missing = validate_binding(
        embedded_binding(doc_missing, emitter_role="third_party"),
        client_settings=settings,
        tool_name="echo",
        public_key=key,
        now=FIXTURE_CLOCK,
    )
    if _crypto_blocked(vr_missing.reason):
        return _skip(sid, name, vr_missing.reason, detail=vr_missing.detail)
    if vr_missing.valid or vr_missing.reason != "args_hash":
        return _fail(
            sid,
            name,
            "expected_args_hash_fail",
            detail=f"got valid={vr_missing.valid} reason={vr_missing.reason}",
        )

    # Present args_hash → pass
    digest = args_hash_for({"text": "t15"})
    claim_ok = build_claim(
        tool_name="echo",
        server_id="toa-conformance-fake",
        decision_id="t15-ok",
        agent_id="00000000-0000-0000-0000-0000000000c1",
        layers=layers,
        emitter_name=CONFORMANCE_EMITTER_NAME,
        emitter_key_id="test-v1",
        reasons=["t15-ok"],
        disposition="delivered",
        args_hash=digest,
    )
    doc_ok = sign_document(claim_ok, private_key=priv_path, public_key_id="test-v1")
    vr_ok = validate_binding(
        embedded_binding(doc_ok, emitter_role="third_party"),
        client_settings=ClientToaSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter=CONFORMANCE_EMITTER_NAME,
            require_args_hash=True,
            expected_args_hash=digest,
        ),
        tool_name="echo",
        public_key=key,
        now=FIXTURE_CLOCK,
    )
    if _crypto_blocked(vr_ok.reason):
        return _skip(sid, name, vr_ok.reason, detail=vr_ok.detail)
    if not vr_ok.valid:
        return _fail(sid, name, vr_ok.reason, detail=vr_ok.detail)

    return _pass(sid, name, checks={"missing": "PASS", "present": "PASS"})


def scenario_t16_key_pin_classes() -> ScenarioResult:
    """T16 — key_unavailable / untrusted_key ≠ attestation_gap; pins on NegotiationRecord."""
    sid, name = "T16", "toa-key-pin-and-verify-classes"
    from pathlib import Path

    from toa_ext.attach import build_claim, embedded_binding
    from toa_ext.negotiation import (
        ABSENCE_ATTESTATION_GAP,
        ABSENCE_KEY_UNAVAILABLE,
        ABSENCE_UNTRUSTED_KEY,
        classify_absence,
        key_fingerprint,
        pin_matches_document,
    )
    from toa_verify import sign_document

    priv_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "keys"
        / "toa-conformance-test-v1.private.json"
    )
    pub_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "keys"
        / "toa-conformance-test-v1.json"
    )
    if not priv_path.is_file() or not pub_path.is_file():
        return _skip(sid, name, "missing_keys")

    fp = key_fingerprint(pub_path)
    server = FakeMcpServer(toa=ServerToaSettings(attach="on_require"), advertise_toa=True)
    client = FakeMcpClient(
        toa=ClientToaSettings(require=True, accepted_emitter_roles=["third_party"]),
        server_id="srv-pin",
        pinned_public_key_id="test-v1",
        pinned_key_fingerprint=fp,
        pinned_emitter_name=CONFORMANCE_EMITTER_NAME,
        transport="stdio",
    )
    client.connect(server)
    rec = client.negotiation_record
    if rec is None or rec.get("pinned_key_fingerprint") != fp:
        return _fail(sid, name, "pin_not_recorded", detail=str(rec))
    if rec.get("transport") != "stdio":
        return _fail(sid, name, "transport_not_recorded")

    claim = build_claim(
        tool_name="echo",
        server_id="srv-pin",
        decision_id="t16",
        agent_id="00000000-0000-0000-0000-0000000000c1",
        layers={
            "reach": "pass",
            "invoke": "pass",
            "functional": "pass",
            "shape": "n/a",
            "openapi_fidelity": "n/a",
            "compositional": "n/a",
        },
        emitter_name=CONFORMANCE_EMITTER_NAME,
        emitter_key_id="test-v1",
        reasons=["t16"],
        disposition="delivered",
    )
    doc = sign_document(claim, private_key=priv_path, public_key_id="test-v1")

    # Attestation present, no trusted key → key_unavailable (not gap)
    c_no_key = classify_absence(
        negotiation=rec,
        attestation_present=True,
        document=doc,
        attach_expected=True,
        public_key_available=False,
    )
    if c_no_key.get("class") != ABSENCE_KEY_UNAVAILABLE:
        return _fail(sid, name, "expected_key_unavailable", detail=str(c_no_key))

    # Wrong pin → untrusted_key
    bad_pin = dict(rec)
    bad_pin["pinned_public_key_id"] = "other-v1"
    match = pin_matches_document(bad_pin, doc, public_key=pub_path)
    if match is not False:
        return _fail(sid, name, "expected_pin_mismatch", detail=str(match))
    c_bad = classify_absence(
        negotiation=rec,
        attestation_present=True,
        document=doc,
        attach_expected=True,
        public_key_available=True,
        key_matches_pin=False,
    )
    if c_bad.get("class") != ABSENCE_UNTRUSTED_KEY:
        return _fail(sid, name, "expected_untrusted_key", detail=str(c_bad))

    # Distinct from attestation_gap
    c_gap = classify_absence(
        negotiation=rec,
        attestation_present=False,
        attach_expected=True,
    )
    if c_gap.get("class") != ABSENCE_ATTESTATION_GAP:
        return _fail(sid, name, "expected_gap", detail=str(c_gap))
    if c_no_key["class"] == c_gap["class"] or c_bad["class"] == c_gap["class"]:
        return _fail(sid, name, "classes_collapsed")

    # Good pin matches
    if pin_matches_document(rec, doc, public_key=pub_path) is not True:
        return _fail(sid, name, "good_pin_should_match")

    # Binding still validates with real key (sanity)
    vr = validate_binding(
        embedded_binding(doc, emitter_role="third_party"),
        client_settings=ClientToaSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter=CONFORMANCE_EMITTER_NAME,
        ),
        tool_name="echo",
        public_key=_public_key_material(),
    )
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if not vr.valid:
        return _fail(sid, name, vr.reason, detail=vr.detail)

    return _pass(
        sid,
        name,
        checks={
            "pin": "PASS",
            "key_unavailable": "PASS",
            "untrusted_key": "PASS",
            "distinct": "PASS",
        },
    )


def scenario_t17_inconsistent_disposition_layers() -> ScenarioResult:
    """T17 — delivered + failing core layer is inconsistent_claims, not positive."""
    sid, name = "T17", "toa-inconsistent-disposition-layers"
    from toa_ext.negotiation import (
        ABSENCE_INCONSISTENT,
        ABSENCE_POSITIVE,
        classify_absence,
        document_claims_are_inconsistent,
        document_is_negative_evidence,
        negotiation_from_initialize,
    )

    rec = negotiation_from_initialize(
        {
            "protocolVersion": "2026-07-28",
            "capabilities": {"extensions": {EXTENSION_ID: {"attach": "on_require"}}},
        },
        server_id="srv-inconsistent",
    )
    doc = {"disposition": "delivered", "layers": {"functional": "fail"}}
    if document_is_negative_evidence(doc) is not True:
        return _fail(sid, name, "helper_still_short_circuits_delivered")
    if document_claims_are_inconsistent(doc) is not True:
        return _fail(sid, name, "conflict_not_flagged")
    classified = classify_absence(
        negotiation=rec,
        attestation_present=True,
        document=doc,
        attach_expected=True,
    )
    if classified.get("class") != ABSENCE_INCONSISTENT:
        return _fail(sid, name, "expected_inconsistent_claims", detail=str(classified))
    if classified["class"] == ABSENCE_POSITIVE:
        return _fail(sid, name, "conflict_classified_positive")
    return _pass(sid, name, checks={"helper": "PASS", "class": ABSENCE_INCONSISTENT})


def scenario_t18_explicit_revocation_policy() -> ScenarioResult:
    """T18 — revoke reading is per-verifier; unspecified does not inherit a default."""
    sid, name = "T18", "toa-explicit-revocation-policy"
    from datetime import datetime, timezone

    from toa_ext.negotiation import (
        REVOCATION_INVALID_IF_REVOKED_NOW,
        REVOCATION_VALID_AT_OBSERVED,
        evaluate_revocation,
        negotiation_from_initialize,
    )

    unspecified = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
    )
    if unspecified.get("acceptable") or unspecified.get("reason") != "revocation_policy_unspecified":
        return _fail(sid, name, "unspecified_must_not_inherit", detail=str(unspecified))

    ledger = negotiation_from_initialize(
        {
            "protocolVersion": "2026-07-28",
            "capabilities": {"extensions": {EXTENSION_ID: {"attach": "on_require"}}},
        },
        server_id="srv-ledger",
        revocation_policy=REVOCATION_VALID_AT_OBSERVED,
    )
    if ledger.get("revocation_policy") != REVOCATION_VALID_AT_OBSERVED:
        return _fail(sid, name, "ledger_policy_not_recorded")
    ledger_ok = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
        negotiation=ledger,
    )
    if not ledger_ok.get("acceptable"):
        return _fail(sid, name, "ledger_should_accept_pre_revoke", detail=str(ledger_ok))

    gate = negotiation_from_initialize(
        {
            "protocolVersion": "2026-07-28",
            "capabilities": {"extensions": {EXTENSION_ID: {"attach": "on_require"}}},
        },
        server_id="srv-gate",
        revocation_policy=REVOCATION_INVALID_IF_REVOKED_NOW,
    )
    gate_now = evaluate_revocation(
        observed_at="2026-01-01T00:00:00Z",
        key_revoked_at="2026-06-01T00:00:00Z",
        negotiation=gate,
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    if gate_now.get("acceptable"):
        return _fail(sid, name, "gate_should_reject_revoked_now", detail=str(gate_now))

    return _pass(
        sid,
        name,
        checks={"unspecified": "PASS", "ledger": "PASS", "gate": "PASS"},
    )


SCENARIOS: List[tuple[str, str, Callable[[], ScenarioResult]]] = [
    ("T1", "toa-capability-advertisement", scenario_t1_advertisement),
    ("T2", "toa-attach-on-require", scenario_t2_attach_on_require),
    ("T3", "toa-require-missing-fails-closed", scenario_t3_require_missing_fails_closed),
    ("T4", "toa-role-pinning-rejects-server", scenario_t4_role_pinning_rejects_server),
    ("T5", "toa-signature-invalid", scenario_t5_signature_invalid),
    ("T6", "toa-min-layers-functional", scenario_t6_min_layers_functional),
    ("T7", "toa-max-age", scenario_t7_max_age),
    ("T8", "toa-reference-hash-mismatch", scenario_t8_reference_hash_mismatch),
    ("T9", "toa-graceful-degradation", scenario_t9_graceful_degradation),
    ("T10", "toa-require-emitter-name", scenario_t10_require_emitter_name),
    ("T11", "toa-negotiation-record", scenario_t11_negotiation_record),
    ("T12", "toa-signed-negative-disposition", scenario_t12_signed_negative_disposition),
    ("T13", "toa-absence-vs-never-advertised", scenario_t13_absence_vs_never_advertised),
    ("T14", "toa-optional-args-hash", scenario_t14_optional_args_hash),
    ("T15", "toa-require-args-hash", scenario_t15_require_args_hash),
    ("T16", "toa-key-pin-and-verify-classes", scenario_t16_key_pin_classes),
    ("T17", "toa-inconsistent-disposition-layers", scenario_t17_inconsistent_disposition_layers),
    ("T18", "toa-explicit-revocation-policy", scenario_t18_explicit_revocation_policy),
]
