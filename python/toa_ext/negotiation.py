"""
NegotiationRecord (`toa-negotiation/0.1`) and offline absence classification.

Closes the silence gap: clients MUST record whether a server advertised TOA so
"never supported" is distinct from "advertised but missing attestation."
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence

NEGOTIATION_SPEC = "toa-negotiation/0.1"
EXTENSION_ID = "dev.agentstatus/toa"

ABSENCE_OUTSIDE_TOA = "outside_toa"
ABSENCE_ATTESTATION_GAP = "attestation_gap"
ABSENCE_POSITIVE = "positive_evidence"
ABSENCE_NEGATIVE = "negative_evidence"
ABSENCE_NO_ATTESTATION_OPTIONAL = "no_attestation_optional"

NEGATIVE_DISPOSITIONS = frozenset({"failed", "refused", "unavailable"})
POSITIVE_DISPOSITIONS = frozenset({"delivered"})
CORE_LAYERS = ("reach", "invoke", "functional")


def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_negotiation_record(
    *,
    server_id: str,
    protocol_version: str,
    server_advertised_toa: bool,
    server_settings: Optional[Mapping[str, Any]] = None,
    client_settings: Optional[Mapping[str, Any]] = None,
    discover_request_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a client-local NegotiationRecord (§13.2)."""
    if not server_id:
        raise ValueError("server_id is required")
    if not protocol_version:
        raise ValueError("protocol_version is required")
    record: Dict[str, Any] = {
        "spec": NEGOTIATION_SPEC,
        "recorded_at": recorded_at or _utc_now_rfc3339(),
        "protocol_version": protocol_version,
        "server_id": server_id,
        "server_advertised_toa": bool(server_advertised_toa),
        "server_settings": dict(server_settings) if server_settings is not None else None,
        "client_settings": dict(client_settings) if client_settings is not None else None,
        "discover_request_id": discover_request_id,
    }
    return record


def negotiation_from_initialize(
    initialize_result: Mapping[str, Any],
    *,
    server_id: str,
    client_settings: Optional[Mapping[str, Any]] = None,
    discover_request_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Derive NegotiationRecord from an MCP initialize / discover result.

    Looks for ``capabilities.extensions["dev.agentstatus/toa"]``.
    """
    protocol = initialize_result.get("protocolVersion") or initialize_result.get(
        "protocol_version"
    )
    if not isinstance(protocol, str) or not protocol:
        raise ValueError("initialize_result missing protocolVersion")

    caps = initialize_result.get("capabilities") or {}
    if not isinstance(caps, Mapping):
        caps = {}
    extensions = caps.get("extensions") or {}
    if not isinstance(extensions, Mapping):
        extensions = {}
    raw = extensions.get(EXTENSION_ID)
    advertised = isinstance(raw, Mapping)
    server_settings = dict(raw) if advertised else None
    return build_negotiation_record(
        server_id=server_id,
        protocol_version=protocol,
        server_advertised_toa=advertised,
        server_settings=server_settings,
        client_settings=client_settings,
        discover_request_id=discover_request_id,
        recorded_at=recorded_at,
    )


def validate_negotiation_record(record: Any) -> Dict[str, Any]:
    """Structural validation aligned with toa-negotiation-0.1.schema.json."""
    if not isinstance(record, Mapping):
        return {"valid": False, "reason": "not_object"}
    if record.get("spec") != NEGOTIATION_SPEC:
        return {"valid": False, "reason": "spec_mismatch", "got": record.get("spec")}
    for field in ("recorded_at", "protocol_version", "server_id"):
        val = record.get(field)
        if not isinstance(val, str) or not val:
            return {"valid": False, "reason": f"missing_or_invalid_{field}"}
    if not isinstance(record.get("server_advertised_toa"), bool):
        return {"valid": False, "reason": "missing_or_invalid_server_advertised_toa"}
    return {"valid": True, "reason": "ok"}


def document_is_negative_evidence(document: Mapping[str, Any]) -> bool:
    """True if disposition or core layers assert a negative outcome (§14.2)."""
    disposition = document.get("disposition")
    if disposition in NEGATIVE_DISPOSITIONS:
        return True
    if disposition in POSITIVE_DISPOSITIONS:
        return False
    layers = document.get("layers") if isinstance(document.get("layers"), Mapping) else {}
    for layer in CORE_LAYERS:
        if layers.get(layer) == "fail":
            return True
    return False


def classify_absence(
    *,
    negotiation: Mapping[str, Any],
    attestation_present: bool,
    document: Optional[Mapping[str, Any]] = None,
    attach_expected: bool = True,
) -> Dict[str, Any]:
    """
    Offline absence class for one call (§13.3).

    Returns ``{"class": ..., "reason": ...}`` where class is one of:
    ``outside_toa``, ``attestation_gap``, ``positive_evidence``,
    ``negative_evidence``, ``no_attestation_optional``.
    """
    shape = validate_negotiation_record(negotiation)
    if not shape.get("valid"):
        return {
            "class": None,
            "reason": "invalid_negotiation_record",
            "detail": shape.get("reason"),
        }

    advertised = bool(negotiation["server_advertised_toa"])

    if not advertised:
        if attestation_present and isinstance(document, Mapping):
            # Unexpected evidence from a non-TOA session — still classify the doc.
            if document_is_negative_evidence(document):
                return {"class": ABSENCE_NEGATIVE, "reason": "unexpected_negative_from_non_toa"}
            return {"class": ABSENCE_POSITIVE, "reason": "unexpected_positive_from_non_toa"}
        return {"class": ABSENCE_OUTSIDE_TOA, "reason": "server_never_advertised_toa"}

    if not attestation_present:
        if attach_expected:
            return {
                "class": ABSENCE_ATTESTATION_GAP,
                "reason": "advertised_but_missing_attestation",
            }
        return {
            "class": ABSENCE_NO_ATTESTATION_OPTIONAL,
            "reason": "advertised_attach_not_required",
        }

    if not isinstance(document, Mapping):
        return {
            "class": ABSENCE_ATTESTATION_GAP,
            "reason": "attestation_flag_without_document",
        }

    if document_is_negative_evidence(document):
        return {"class": ABSENCE_NEGATIVE, "reason": "signed_negative_outcome"}
    return {"class": ABSENCE_POSITIVE, "reason": "signed_positive_outcome"}


def classes_are_distinct() -> Sequence[str]:
    """Sanity helper used by conformance: gap ≠ outside."""
    return (ABSENCE_OUTSIDE_TOA, ABSENCE_ATTESTATION_GAP)
