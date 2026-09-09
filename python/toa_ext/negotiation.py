"""
NegotiationRecord (`toa-negotiation/0.1`) and offline outcome classification.

Closes the silence gap: clients MUST record whether a server advertised TOA so
"never supported" is distinct from "advertised but missing attestation."

Also records optional key pins so "cannot verify" is distinct from "did not
attest," and defines revocation evaluation for already-signed evidence.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union

NEGOTIATION_SPEC = "toa-negotiation/0.1"
EXTENSION_ID = "dev.agentstatus/toa"

ABSENCE_OUTSIDE_TOA = "outside_toa"
ABSENCE_ATTESTATION_GAP = "attestation_gap"
ABSENCE_POSITIVE = "positive_evidence"
ABSENCE_NEGATIVE = "negative_evidence"
ABSENCE_NO_ATTESTATION_OPTIONAL = "no_attestation_optional"
ABSENCE_KEY_UNAVAILABLE = "key_unavailable"
ABSENCE_UNTRUSTED_KEY = "untrusted_key"
ABSENCE_INCONSISTENT = "inconsistent_claims"

# Both policies are defined. Neither is inherited when the field is absent.
REVOCATION_VALID_AT_OBSERVED = "valid_at_observed_at"
REVOCATION_INVALID_IF_REVOKED_NOW = "invalid_if_revoked_now"
REVOCATION_POLICIES = frozenset(
    {REVOCATION_VALID_AT_OBSERVED, REVOCATION_INVALID_IF_REVOKED_NOW}
)

NEGATIVE_DISPOSITIONS = frozenset({"failed", "refused", "unavailable"})
POSITIVE_DISPOSITIONS = frozenset({"delivered"})
CORE_LAYERS = ("reach", "invoke", "functional")
TRANSPORTS = frozenset({"stdio", "http", "sse", "other"})

KeyMaterial = Union[str, bytes, Mapping[str, Any], Path]


def _utc_now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_public_key_raw(key: KeyMaterial) -> bytes:
    if isinstance(key, Path):
        return _load_public_key_raw(json.loads(key.read_text(encoding="utf-8")))
    if isinstance(key, Mapping):
        raw = key.get("public_key") or key.get("key")
        if not raw:
            raise ValueError("key object missing public_key")
        return _load_public_key_raw(raw)
    if isinstance(key, bytes):
        if len(key) == 32:
            return key
        return base64.b64decode(key)
    if isinstance(key, str):
        s = key.strip()
        if s.startswith("{"):
            return _load_public_key_raw(json.loads(s))
        return base64.b64decode(s)
    raise TypeError(f"unsupported key type: {type(key)}")


def key_fingerprint(public_key: KeyMaterial) -> str:
    """sha256: hex of the raw public key bytes (Ed25519: 32 bytes)."""
    digest = hashlib.sha256(_load_public_key_raw(public_key)).hexdigest()
    return f"sha256:{digest}"


def build_negotiation_record(
    *,
    server_id: str,
    protocol_version: str,
    server_advertised_toa: bool,
    server_settings: Optional[Mapping[str, Any]] = None,
    client_settings: Optional[Mapping[str, Any]] = None,
    discover_request_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    pinned_public_key_id: Optional[str] = None,
    pinned_key_fingerprint: Optional[str] = None,
    pinned_emitter_name: Optional[str] = None,
    transport: Optional[str] = None,
    revocation_policy: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a client-local NegotiationRecord (§13.2)."""
    if not server_id:
        raise ValueError("server_id is required")
    if not protocol_version:
        raise ValueError("protocol_version is required")
    if transport is not None and transport not in TRANSPORTS:
        raise ValueError(f"invalid transport: {transport}")
    if revocation_policy is not None and revocation_policy not in REVOCATION_POLICIES:
        raise ValueError(f"invalid revocation_policy: {revocation_policy}")
    record: Dict[str, Any] = {
        "spec": NEGOTIATION_SPEC,
        "recorded_at": recorded_at or _utc_now_rfc3339(),
        "protocol_version": protocol_version,
        "server_id": server_id,
        "server_advertised_toa": bool(server_advertised_toa),
        "server_settings": dict(server_settings) if server_settings is not None else None,
        "client_settings": dict(client_settings) if client_settings is not None else None,
        "discover_request_id": discover_request_id,
        "pinned_public_key_id": pinned_public_key_id,
        "pinned_key_fingerprint": pinned_key_fingerprint,
        "pinned_emitter_name": pinned_emitter_name,
        "transport": transport,
        "revocation_policy": revocation_policy,
    }
    return record


def negotiation_from_initialize(
    initialize_result: Mapping[str, Any],
    *,
    server_id: str,
    client_settings: Optional[Mapping[str, Any]] = None,
    discover_request_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    pinned_public_key_id: Optional[str] = None,
    pinned_key_fingerprint: Optional[str] = None,
    pinned_emitter_name: Optional[str] = None,
    transport: Optional[str] = None,
    revocation_policy: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Derive NegotiationRecord from an MCP initialize / discover result.

    Looks for ``capabilities.extensions["dev.agentstatus/toa"]``.
    Key pin fields are client-supplied (out-of-band trust), not taken from the
    server advertisement.
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
        pinned_public_key_id=pinned_public_key_id,
        pinned_key_fingerprint=pinned_key_fingerprint,
        pinned_emitter_name=pinned_emitter_name,
        transport=transport,
        revocation_policy=revocation_policy,
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
    transport = record.get("transport")
    if transport is not None and transport not in TRANSPORTS:
        return {"valid": False, "reason": "invalid_transport", "got": transport}
    fp = record.get("pinned_key_fingerprint")
    if fp is not None:
        if not isinstance(fp, str) or not fp.startswith("sha256:"):
            return {"valid": False, "reason": "invalid_pinned_key_fingerprint"}
    policy = record.get("revocation_policy")
    if policy is not None and policy not in REVOCATION_POLICIES:
        return {"valid": False, "reason": "invalid_revocation_policy", "got": policy}
    return {"valid": True, "reason": "ok"}


def document_has_failing_core_layer(document: Mapping[str, Any]) -> bool:
    layers = document.get("layers") if isinstance(document.get("layers"), Mapping) else {}
    return any(layers.get(layer) == "fail" for layer in CORE_LAYERS)


def document_claims_are_inconsistent(document: Mapping[str, Any]) -> bool:
    """
    True when disposition and core layers contradict (§14.2).

    ``disposition=delivered`` plus any core layer ``fail`` is inconsistent.
    Failed required layers do not become positive just because disposition says
    delivered. The offline class for that document is ``inconsistent_claims``,
    not ``positive_evidence``.
    """
    return (
        document.get("disposition") in POSITIVE_DISPOSITIONS
        and document_has_failing_core_layer(document)
    )


def document_is_negative_evidence(document: Mapping[str, Any]) -> bool:
    """True if disposition or core layers assert a negative outcome (§14.2)."""
    if document.get("disposition") in NEGATIVE_DISPOSITIONS:
        return True
    return document_has_failing_core_layer(document)


def _parse_rfc3339(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def revocation_policy_from_record(negotiation: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Read ``revocation_policy`` from a NegotiationRecord. Absent → None."""
    if not isinstance(negotiation, Mapping):
        return None
    policy = negotiation.get("revocation_policy")
    if policy is None:
        return None
    if policy not in REVOCATION_POLICIES:
        return None
    return str(policy)


def evaluate_revocation(
    *,
    observed_at: Any,
    key_revoked_at: Optional[Any] = None,
    policy: Optional[str] = None,
    now: Optional[datetime] = None,
    negotiation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Decide whether already-signed evidence remains acceptable after key revoke.

    Both policies are defined. Neither is a global default:

    - ``valid_at_observed_at``: historically acceptable if the key was still
      trusted at ``observed_at`` (ledger / archive).
    - ``invalid_if_revoked_now``: reject if the key is revoked at verify time
      (action gates).

    Policy comes from ``policy`` or ``negotiation.revocation_policy``. If a
    revoke timestamp is present and no policy was declared, return
    ``revocation_policy_unspecified`` (fail closed). Two verifiers MUST NOT
    silently pick different readings.
    """
    declared = policy if policy is not None else revocation_policy_from_record(negotiation)

    if key_revoked_at is None:
        return {"acceptable": True, "reason": "key_not_revoked", "policy": declared}

    if declared is None:
        return {
            "acceptable": False,
            "reason": "revocation_policy_unspecified",
            "policy": None,
        }
    if declared not in REVOCATION_POLICIES:
        return {
            "acceptable": False,
            "reason": "unknown_revocation_policy",
            "policy": declared,
        }

    revoked = _parse_rfc3339(key_revoked_at)
    observed = _parse_rfc3339(observed_at)
    if revoked is None:
        return {"acceptable": False, "reason": "invalid_key_revoked_at", "policy": declared}
    if observed is None:
        return {"acceptable": False, "reason": "invalid_observed_at", "policy": declared}

    if declared == REVOCATION_INVALID_IF_REVOKED_NOW:
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=timezone.utc)
        if clock >= revoked:
            return {"acceptable": False, "reason": "key_revoked_now", "policy": declared}
        return {"acceptable": True, "reason": "key_not_yet_revoked", "policy": declared}

    if observed >= revoked:
        return {
            "acceptable": False,
            "reason": "key_already_revoked_at_observed_at",
            "policy": REVOCATION_VALID_AT_OBSERVED,
        }
    return {
        "acceptable": True,
        "reason": "valid_as_of_observed_at",
        "policy": REVOCATION_VALID_AT_OBSERVED,
    }


def pin_matches_document(
    negotiation: Mapping[str, Any],
    document: Mapping[str, Any],
    *,
    public_key: Optional[KeyMaterial] = None,
) -> Optional[bool]:
    """
    Compare document emitter/key id (and optional live key fingerprint) to pin.

    Returns None if no pin fields are present on the NegotiationRecord.
    """
    pin_id = negotiation.get("pinned_public_key_id")
    pin_fp = negotiation.get("pinned_key_fingerprint")
    pin_emitter = negotiation.get("pinned_emitter_name")
    if pin_id is None and pin_fp is None and pin_emitter is None:
        return None

    emitter = document.get("emitter") if isinstance(document.get("emitter"), Mapping) else {}
    if pin_emitter is not None and emitter.get("name") != pin_emitter:
        return False
    doc_key_id = document.get("public_key_id") or emitter.get("key_id")
    if pin_id is not None and doc_key_id != pin_id:
        return False
    if pin_fp is not None:
        if public_key is None:
            return False
        try:
            if key_fingerprint(public_key) != pin_fp:
                return False
        except Exception:
            return False
    return True


def classify_absence(
    *,
    negotiation: Mapping[str, Any],
    attestation_present: bool,
    document: Optional[Mapping[str, Any]] = None,
    attach_expected: bool = True,
    public_key_available: bool = True,
    key_matches_pin: Optional[bool] = None,
    verify_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Offline outcome class for one call (§13.3 / §15).

    Returns ``{"class": ..., "reason": ...}`` where class is one of:
    ``outside_toa``, ``attestation_gap``, ``positive_evidence``,
    ``negative_evidence``, ``no_attestation_optional``,
    ``key_unavailable``, ``untrusted_key``, ``inconsistent_claims``.

    ``key_unavailable`` / ``untrusted_key`` MUST NOT be collapsed into
    ``attestation_gap``. ``disposition=delivered`` plus a failing core
    layer is ``inconsistent_claims``, not ``positive_evidence``.
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
            if document_claims_are_inconsistent(document):
                return {
                    "class": ABSENCE_INCONSISTENT,
                    "reason": "disposition_delivered_with_failing_core_layer",
                }
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

    # Key / trust failures: distinct from attestation_gap.
    if not public_key_available:
        return {
            "class": ABSENCE_KEY_UNAVAILABLE,
            "reason": "attestation_present_but_no_trusted_key",
        }
    if key_matches_pin is False:
        return {
            "class": ABSENCE_UNTRUSTED_KEY,
            "reason": "document_key_does_not_match_negotiation_pin",
        }
    if verify_reason in {"invalid_signature", "no_public_key_configured"} or (
        isinstance(verify_reason, str) and verify_reason.startswith("unsupported_algorithm")
    ):
        if verify_reason == "no_public_key_configured":
            return {
                "class": ABSENCE_KEY_UNAVAILABLE,
                "reason": "no_public_key_configured",
            }
        return {
            "class": ABSENCE_UNTRUSTED_KEY,
            "reason": str(verify_reason),
        }

    if document_claims_are_inconsistent(document):
        return {
            "class": ABSENCE_INCONSISTENT,
            "reason": "disposition_delivered_with_failing_core_layer",
        }
    if document_is_negative_evidence(document):
        return {"class": ABSENCE_NEGATIVE, "reason": "signed_negative_outcome"}
    return {"class": ABSENCE_POSITIVE, "reason": "signed_positive_outcome"}


def classes_are_distinct() -> Sequence[str]:
    """Sanity helper: gap ≠ outside ≠ key failures ≠ inconsistent."""
    return (
        ABSENCE_OUTSIDE_TOA,
        ABSENCE_ATTESTATION_GAP,
        ABSENCE_KEY_UNAVAILABLE,
        ABSENCE_UNTRUSTED_KEY,
        ABSENCE_INCONSISTENT,
    )
