"""
Sign `toa/0.1` documents (reference / conformance emitters).

Production AgentStatus signing stays on the product API. This module is for
reference SDK attach paths and regenerating conformance fixtures.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Union

from .verify import claim_for_signing, canonical_json

PrivateKeyMaterial = Union[str, bytes, Mapping[str, Any], Path]


def _load_private_key_bytes(key: PrivateKeyMaterial) -> bytes:
    if isinstance(key, Path):
        return _load_private_key_bytes(json.loads(key.read_text(encoding="utf-8")))
    if isinstance(key, Mapping):
        raw = key.get("private_key") or key.get("key")
        if not raw:
            raise ValueError("key object missing private_key")
        return _load_private_key_bytes(raw)
    if isinstance(key, bytes):
        if len(key) == 32:
            return key
        return base64.b64decode(key)
    if isinstance(key, str):
        s = key.strip()
        if s.startswith("{"):
            return _load_private_key_bytes(json.loads(s))
        if "BEGIN" in s:
            from cryptography.hazmat.primitives import serialization

            loaded = serialization.load_pem_private_key(s.encode("utf-8"), password=None)
            return loaded.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        return base64.b64decode(s)
    raise TypeError(f"unsupported private key type: {type(key)}")


def payload_hash_for_claim(claim: Mapping[str, Any]) -> str:
    """sha256: hex of canonical JSON of signed claim fields."""
    body = claim_for_signing(claim)
    digest = hashlib.sha256(canonical_json(body)).hexdigest()
    return f"sha256:{digest}"


def sign_document(
    claim: Mapping[str, Any],
    *,
    private_key: PrivateKeyMaterial,
    public_key_id: str | None = None,
) -> Dict[str, Any]:
    """
    Return a full `toa/0.1` document with signature + payload_hash.

    `claim` must include all signed fields (see SPEC / SIGNED_KEYS). Envelope
    fields are added here.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    body = claim_for_signing(claim)
    for required in ("spec", "toa_id", "tool", "run", "observed_at", "layers", "emitter"):
        if required not in body:
            raise ValueError(f"missing signed field: {required}")

    priv = Ed25519PrivateKey.from_private_bytes(_load_private_key_bytes(private_key))
    sig = base64.b64encode(priv.sign(canonical_json(body))).decode("ascii")
    emitter = body.get("emitter") if isinstance(body.get("emitter"), dict) else {}
    key_id = public_key_id or emitter.get("key_id") or "v1"

    return {
        **body,
        "payload_hash": payload_hash_for_claim(body),
        "signature": sig,
        "public_key_id": key_id,
    }
