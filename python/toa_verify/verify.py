"""
Verify Tool Outcome Attestation documents (toa/0.1).

Signature is Ed25519 over canonical JSON of the signed claim fields
(sorted keys, no whitespace). Envelope fields signature / payload_hash /
public_key_id are not part of the signed body.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
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
    # Prefer key shipped inside the installed package (pip subdirectory=python).
    packaged = Path(__file__).resolve().parent / "keys" / "agentstatus-v1.json"
    if packaged.is_file():
        return packaged
    # Dev checkout layout: <repo>/python/toa_verify/ -> <repo>/keys/
    return Path(__file__).resolve().parents[2] / "keys" / "agentstatus-v1.json"



def parse_max_age_seconds(value: Union[str, int, float]) -> int:
    """Parse max age as seconds. Accepts int seconds or strings like 3600, 24h, 7d, 90m."""
    if isinstance(value, (int, float)):
        n = int(value)
        if n < 0:
            raise ValueError("max_age must be non-negative")
        return n
    s = str(value).strip().lower()
    if not s:
        raise ValueError("empty max_age")
    m = re.fullmatch(r"(\d+)\s*([smhd]?)", s)
    if not m:
        raise ValueError(f"bad_max_age:{value}")
    n = int(m.group(1))
    unit = m.group(2) or "s"
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return n * mult


def parse_observed_at(value: Any) -> Optional[datetime]:
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


def verify_document(
    document: Mapping[str, Any],
    *,
    public_key: Optional[KeyMaterial] = None,
    require_emitter: Optional[str] = None,
    max_age_seconds: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Verify a TOA document.

    Returns dict with keys: valid (bool), reason (str), and claim fields on success.
    When max_age_seconds is set, observed_at must be within that window of now (UTC).
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

    if max_age_seconds is not None:
        observed = parse_observed_at(body.get("observed_at"))
        if observed is None:
            return {"valid": False, "reason": "missing_or_invalid_observed_at", "claim": body}
        ref = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
        age = (ref - observed).total_seconds()
        if age < 0:
            return {
                "valid": False,
                "reason": "observed_at_in_future",
                "claim": body,
                "age_seconds": age,
            }
        if age > max_age_seconds:
            return {
                "valid": False,
                "reason": "stale_attestation",
                "claim": body,
                "age_seconds": int(age),
                "max_age_seconds": max_age_seconds,
            }

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
