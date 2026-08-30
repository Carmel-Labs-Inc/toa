"""
Verify Tool Outcome Attestation documents (toa/0.1).

Signature is Ed25519 over canonical JSON of the signed claim fields
(sorted keys, no whitespace). Envelope fields signature / payload_hash /
public_key_id are not part of the signed body.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

TOA_SPEC = "toa/0.1"

SIGNED_KEYS = (
    "spec",
    "toa_id",
    "tool",
    "run",
    "observed_at",
    "layers",
    "outcome_grade",
    "business_outcome_ok",
    "reasons",
    "emitter",
)

KeyMaterial = Union[str, bytes, Mapping[str, Any], Path]


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def claim_for_signing(document: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: document[k] for k in SIGNED_KEYS if k in document}


def _load_public_key_bytes(key: KeyMaterial) -> bytes:
    if isinstance(key, Path):
        data = json.loads(key.read_text(encoding="utf-8"))
        return _load_public_key_bytes(data)
    if isinstance(key, Mapping):
        raw = key.get("public_key") or key.get("key")
        if not raw:
            raise ValueError("key object missing public_key")
        return _load_public_key_bytes(raw)
    if isinstance(key, bytes):
        if len(key) == 32:
            return key
        # try base64
        return base64.b64decode(key)
    if isinstance(key, str):
        s = key.strip()
        if s.startswith("{"):
            return _load_public_key_bytes(json.loads(s))
        if "BEGIN" in s:
            from cryptography.hazmat.primitives import serialization

            loaded = serialization.load_pem_public_key(s.encode("utf-8"))
            return loaded.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        return base64.b64decode(s)
    raise TypeError(f"unsupported key type: {type(key)}")


def default_agentstatus_v1_key_path() -> Path:
    return Path(__file__).resolve().parents[2] / "keys" / "agentstatus-v1.json"


def verify_document(
    document: Mapping[str, Any],
    *,
    public_key: Optional[KeyMaterial] = None,
    require_emitter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verify a TOA document.

    Returns dict with keys: valid (bool), reason (str), and claim fields on success.
    """
    if not isinstance(document, Mapping):
        return {"valid": False, "reason": "not_an_object"}

    if document.get("spec") != TOA_SPEC:
        return {"valid": False, "reason": f"unsupported_spec:{document.get('spec')}"}

    signature = document.get("signature")
    if not signature or not isinstance(signature, str):
        return {"valid": False, "reason": "missing_signature"}

    body = claim_for_signing(document)
    emitter = body.get("emitter") if isinstance(body.get("emitter"), dict) else {}
    if require_emitter and emitter.get("name") != require_emitter:
        return {
            "valid": False,
            "reason": f"emitter_mismatch:{emitter.get('name')}",
            "claim": body,
        }

    key_material: KeyMaterial
    if public_key is not None:
        key_material = public_key
    else:
        key_path = default_agentstatus_v1_key_path()
        if not key_path.is_file():
            return {"valid": False, "reason": "no_public_key_configured"}
        key_material = key_path

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub = Ed25519PublicKey.from_public_bytes(_load_public_key_bytes(key_material))
        pub.verify(base64.b64decode(signature), canonical_json(body))
    except InvalidSignature:
        return {"valid": False, "reason": "invalid_signature", "claim": body}
    except Exception as exc:
        return {"valid": False, "reason": f"verify_error:{exc}", "claim": body}

    return {
        "valid": True,
        "reason": "ok",
        "claim": body,
        "toa_id": body.get("toa_id"),
        "layers": body.get("layers"),
        "tool": body.get("tool"),
        "observed_at": body.get("observed_at"),
        "business_outcome_ok": body.get("business_outcome_ok"),
        "outcome_grade": body.get("outcome_grade"),
        "public_key_id": document.get("public_key_id") or emitter.get("key_id"),
    }
