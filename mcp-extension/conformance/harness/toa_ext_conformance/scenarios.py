"""T1–T10 scenario implementations (in-process fake MCP)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping, Optional

from .constants import CONFORMANCE_EMITTER_NAME, EXTENSION_ID
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
    vr = validate_binding(binding, client_settings=client.toa, tool_name="echo", public_key=key)
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
    vr = validate_binding(binding, client_settings=settings, tool_name="echo", public_key=key)
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
    vr = validate_binding(binding, client_settings=settings, tool_name="echo", public_key=key)
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
    vr = validate_binding(binding, client_settings=settings, tool_name="echo", public_key=key)
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

    vr = validate_binding(binding, client_settings=settings, tool_name=tool, public_key=key)
    if _crypto_blocked(vr.reason):
        return _skip(sid, name, vr.reason, detail=vr.detail)
    if vr.valid or vr.reason != "emitter_name":
        return _fail(sid, name, "wrong_reason", detail=f"expected emitter_name got {vr.reason}")
    return _pass(sid, name, checks={"reason": "emitter_name", "mode": expected_detail})

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
]
