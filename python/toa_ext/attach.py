"""
Reference attach path for MCP extension `dev.agentstatus/toa`.

Builds AttestationBinding objects and merges them onto tools/call results
under `_meta["dev.agentstatus/toa"]`, honoring server `attach` policy and
client `require` settings.

This is a reference SDK surface — not AgentStatus production emit.
"""

from __future__ import annotations

import secrets
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence

from toa_verify.sign import sign_document
from toa_verify.verify import KeyMaterial

from .binding import (
    EXTENSION_ID,
    ClientSettings,
    TOA_SPEC,
    validate_binding,
)

TOA_ERROR_CODE = -38100
TOA_ERROR_NAME = "ToaAttestationFailure"


def new_toa_id() -> str:
    return "toa_" + secrets.token_hex(10)


def build_claim(
    *,
    tool_name: str,
    server_id: str,
    decision_id: str,
    agent_id: str,
    layers: Mapping[str, str],
    emitter_name: str,
    emitter_version: str = "0.1.0",
    emitter_key_id: str = "v1",
    observed_at: Optional[str] = None,
    catalog_hash: Optional[str] = None,
    outcome_grade: Optional[str] = None,
    business_outcome_ok: Optional[bool] = None,
    reasons: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Unsigned claim fields for `toa/0.1` (ready for sign_document)."""
    return {
        "spec": TOA_SPEC,
        "toa_id": new_toa_id(),
        "tool": {
            "name": tool_name,
            "server_id": server_id,
            "catalog_hash": catalog_hash,
        },
        "run": {"decision_id": decision_id, "agent_id": agent_id},
        "observed_at": observed_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "layers": dict(layers),
        "outcome_grade": outcome_grade,
        "business_outcome_ok": business_outcome_ok,
        "reasons": list(reasons or []),
        "emitter": {
            "name": emitter_name,
            "version": emitter_version,
            "key_id": emitter_key_id,
        },
    }


def embedded_binding(
    document: Mapping[str, Any],
    *,
    emitter_role: str,
) -> Dict[str, Any]:
    return {
        "mode": "embedded",
        "emitter_role": emitter_role,
        "spec": TOA_SPEC,
        "document": dict(document),
    }


def reference_binding(
    *,
    uri: str,
    document: Mapping[str, Any],
    emitter_role: str,
) -> Dict[str, Any]:
    emitter = document.get("emitter")
    if not isinstance(emitter, Mapping):
        raise ValueError("document missing emitter")
    ph = document.get("payload_hash")
    if not isinstance(ph, str):
        raise ValueError("document missing payload_hash")
    return {
        "mode": "reference",
        "emitter_role": emitter_role,
        "spec": TOA_SPEC,
        "uri": uri,
        "payload_hash": ph,
        "emitter": {
            "name": emitter["name"],
            "version": emitter["version"],
            "key_id": emitter["key_id"],
        },
    }


def attach_binding_to_result(
    result: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Return a copy of a tools/call result with the TOA binding under `_meta`.

    Accepts either a bare result object or a JSON-RPC response with `result`.
    """
    out = deepcopy(dict(result))
    target: MutableMapping[str, Any]
    if "result" in out and isinstance(out["result"], dict) and "jsonrpc" in out:
        target = out["result"]
    else:
        target = out
    meta = dict(target.get("_meta") or {})
    meta[EXTENSION_ID] = dict(binding)
    target["_meta"] = meta
    return out


def toa_failure_error(reason: str, message: Optional[str] = None) -> Dict[str, Any]:
    """JSON-RPC error body for fail-closed require (DECISIONS.md / wire §10)."""
    return {
        "code": TOA_ERROR_CODE,
        "message": message
        or (
            "TOA attestation required"
            if reason == "missing_binding"
            else "TOA attestation invalid"
        ),
        "data": {
            "extensionId": EXTENSION_ID,
            "name": TOA_ERROR_NAME,
            "reason": reason,
        },
    }


def should_attach(
    *,
    server_attach: str,
    client_settings: Optional[ClientSettings],
) -> bool:
    """Whether server policy says to attach for this peer."""
    if server_attach == "never":
        return False
    if server_attach == "always":
        return True
    # on_require
    return bool(client_settings and client_settings.require)


def attach_signed_document(
    result: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    private_key: Any,
    emitter_role: str,
    mode: str = "embedded",
    reference_uri: Optional[str] = None,
    public_key_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Sign claim and attach as embedded or reference binding."""
    document = sign_document(claim, private_key=private_key, public_key_id=public_key_id)
    if mode == "reference":
        if not reference_uri:
            raise ValueError("reference mode requires reference_uri")
        binding = reference_binding(
            uri=reference_uri, document=document, emitter_role=emitter_role
        )
    else:
        binding = embedded_binding(document, emitter_role=emitter_role)
    return attach_binding_to_result(result, binding)


def enforce_client_require(
    result: Mapping[str, Any],
    *,
    client_settings: ClientSettings,
    public_key: Optional[KeyMaterial] = None,
    document_store: Optional[Mapping[str, Mapping[str, Any]]] = None,
    expected_tool_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    If client.require, validate binding on result; on failure return
    `{ "ok": False, "error": toa_failure_error(...) }`.
    On success or require=false: `{ "ok": True, "result": result, "validation": ... }`.
    """
    if not client_settings.require:
        return {"ok": True, "result": result, "validation": None}

    payload = result.get("result") if isinstance(result.get("result"), dict) and "jsonrpc" in result else result
    if not isinstance(payload, Mapping):
        return {"ok": False, "error": toa_failure_error("missing_binding")}

    meta = payload.get("_meta") if isinstance(payload.get("_meta"), Mapping) else {}
    binding = meta.get(EXTENSION_ID) if isinstance(meta, Mapping) else None
    validation = validate_binding(
        binding if isinstance(binding, Mapping) else None,
        settings=client_settings,
        public_key=public_key,
        document_store=document_store,
        expected_tool_name=expected_tool_name,
    )
    if not validation.get("valid"):
        return {
            "ok": False,
            "error": toa_failure_error(str(validation.get("reason") or "missing_binding")),
            "validation": validation,
        }
    return {"ok": True, "result": result, "validation": validation}
