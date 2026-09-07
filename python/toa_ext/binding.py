"""
Validate AttestationBinding for MCP extension `dev.agentstatus/toa`.

Implements the algorithm in mcp-extension/specification/draft/toa-extension.md §8.
Reuses toa_verify for Ed25519 / canonical JSON; does not invent a second grading vocabulary.

Product home: agentstatus.dev. Wire extension id: dev.agentstatus/toa.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional, Sequence, Union

from toa_verify.verify import KeyMaterial, verify_document

EXTENSION_ID = "dev.agentstatus/toa"
TOA_SPEC = "toa/0.1"

VALID_ROLES = frozenset({"third_party", "observer", "server"})
VALID_MODES = frozenset({"embedded", "reference"})
HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")

DocumentStore = Mapping[str, Mapping[str, Any]]
ResolveFn = Callable[[str], Optional[Mapping[str, Any]]]


def default_min_layers() -> Dict[str, str]:
    return {"reach": "pass", "invoke": "pass", "functional": "pass"}


@dataclass
class ClientSettings:
    """Client capability settings for `dev.agentstatus/toa` (§5.1)."""

    require: bool = False
    accepted_emitter_roles: Sequence[str] = field(
        default_factory=lambda: ["third_party", "observer"]
    )
    require_emitter: Optional[str] = None
    max_age_seconds: Optional[int] = 604800
    min_layers: Optional[Mapping[str, str]] = None
    require_args_hash: bool = False
    expected_args_hash: Optional[str] = None

    def effective_min_layers(self) -> Mapping[str, str]:
        if self.min_layers is not None:
            return self.min_layers
        if self.require:
            return default_min_layers()
        return {}


def layer_satisfies(got: Any, required: str) -> bool:
    """§5.1 layer comparison: pass-only / warn accepts pass|warn; n/a never satisfies."""
    if got is None or got == "n/a":
        return False
    if required == "pass":
        return got == "pass"
    if required == "warn":
        return got in ("pass", "warn")
    return got == required


def _fail(reason: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"valid": False, "reason": reason, "extensionId": EXTENSION_ID}
    out.update(extra)
    return out


def _ok(**extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"valid": True, "reason": "ok", "extensionId": EXTENSION_ID}
    out.update(extra)
    return out


def _parse_observed_at(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
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


def _validate_binding_shape(binding: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Structural checks aligned with attestation-binding-0.1.schema.json."""
    mode = binding.get("mode")
    if mode not in VALID_MODES:
        return _fail("missing_binding", detail="invalid_or_missing_mode")
    role = binding.get("emitter_role")
    if role not in VALID_ROLES:
        return _fail("emitter_role", detail="invalid_or_missing_emitter_role")
    if binding.get("spec") != TOA_SPEC:
        return _fail("spec_mismatch", got=binding.get("spec"))
    if mode == "embedded":
        if not isinstance(binding.get("document"), Mapping):
            return _fail("missing_binding", detail="embedded_requires_document")
    else:
        uri = binding.get("uri")
        if not isinstance(uri, str) or not uri:
            return _fail("missing_binding", detail="reference_requires_uri")
        ph = binding.get("payload_hash")
        if not isinstance(ph, str) or not HASH_RE.match(ph):
            return _fail("hash_mismatch", detail="invalid_or_missing_payload_hash")
        emitter = binding.get("emitter")
        if not isinstance(emitter, Mapping):
            return _fail("emitter_name", detail="reference_requires_emitter")
        for k in ("name", "version", "key_id"):
            if k not in emitter:
                return _fail("emitter_name", detail=f"reference_emitter_missing_{k}")
    return None


def _default_fixture_store(fixtures_dir: Optional[Path] = None) -> DocumentStore:
    root = fixtures_dir or (
        Path(__file__).resolve().parents[2]
        / "mcp-extension"
        / "conformance"
        / "fixtures"
    )
    store: MutableMapping[str, Mapping[str, Any]] = {}
    if not root.is_dir():
        return store
    for path in root.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, Mapping):
            store[f"fixture:{path.stem}"] = doc
            store[path.stem] = doc
    return store


def resolve_document(
    binding: Mapping[str, Any],
    *,
    document_store: Optional[DocumentStore] = None,
    resolve: Optional[ResolveFn] = None,
) -> tuple[Optional[Mapping[str, Any]], Optional[Dict[str, Any]]]:
    """Resolve embedded or reference binding to a toa/0.1 document."""
    mode = binding.get("mode")
    if mode == "embedded":
        doc = binding.get("document")
        if isinstance(doc, Mapping):
            return doc, None
        return None, _fail("missing_binding", detail="embedded_document_missing")

    uri = binding.get("uri")
    if not isinstance(uri, str):
        return None, _fail("missing_binding", detail="reference_uri_missing")

    if resolve is not None:
        doc = resolve(uri)
        if doc is not None:
            return doc, None

    store = document_store if document_store is not None else _default_fixture_store()
    doc = store.get(uri)
    if doc is None and uri.startswith("fixture:"):
        doc = store.get(uri[len("fixture:") :])
    if not isinstance(doc, Mapping):
        return None, _fail("missing_binding", detail=f"unresolved_uri:{uri}")
    return doc, None


def validate_binding(
    binding: Optional[Mapping[str, Any]],
    *,
    settings: Optional[ClientSettings] = None,
    public_key: Optional[KeyMaterial] = None,
    document_store: Optional[DocumentStore] = None,
    resolve: Optional[ResolveFn] = None,
    now: Optional[datetime] = None,
    expected_tool_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate an AttestationBinding against client settings (§8).

    Returns dict with `valid`, `reason` (ok | missing_binding | invalid_signature |
    emitter_role | emitter_name | expired | min_layers | hash_mismatch | spec_mismatch),
    and `extensionId`.
    """
    cfg = settings or ClientSettings()

    if binding is None:
        if cfg.require:
            return _fail("missing_binding")
        return _ok(optional=True)

    if not isinstance(binding, Mapping):
        if cfg.require:
            return _fail("missing_binding", detail="binding_not_object")
        return _ok(optional=True, ignored=True)

    shape_err = _validate_binding_shape(binding)
    if shape_err is not None:
        return shape_err

    document, resolve_err = resolve_document(
        binding, document_store=document_store, resolve=resolve
    )
    if resolve_err is not None:
        return resolve_err
    assert document is not None

    # §8.2 spec
    if document.get("spec") != TOA_SPEC:
        return _fail("spec_mismatch", got=document.get("spec"))

    # §8.3 signature (reuse toa_verify)
    if public_key is None:
        return _fail("invalid_signature", detail="no_public_key_configured")
    verify = verify_document(
        document,
        public_key=public_key,
        require_args_hash=cfg.require_args_hash,
        expected_args_hash=cfg.expected_args_hash,
    )
    if not verify.get("valid"):
        reason = verify.get("reason") or "invalid_signature"
        if reason == "missing_args_hash" or reason == "invalid_args_hash" or reason == "args_hash_mismatch":
            return _fail("args_hash", verify_reason=reason)
        if isinstance(reason, str) and reason.startswith("unsupported_algorithm"):
            return _fail("unsupported_algorithm", verify_reason=reason)
        if reason == "invalid_signature" or str(reason).startswith("verify_error"):
            return _fail("invalid_signature", verify_reason=reason)
        if str(reason).startswith("unsupported_spec"):
            return _fail("spec_mismatch", verify_reason=reason)
        return _fail("invalid_signature", verify_reason=reason)

    # §9.4 tool correlation
    if expected_tool_name is not None:
        tool = document.get("tool") if isinstance(document.get("tool"), dict) else {}
        if tool.get("name") != expected_tool_name:
            return _fail(
                "missing_binding",
                detail="tool_name_mismatch",
                got=tool.get("name"),
                expected=expected_tool_name,
            )

    # §8.4 emitter_role
    role = binding.get("emitter_role")
    accepted = list(cfg.accepted_emitter_roles)
    if role not in accepted:
        return _fail("emitter_role", emitter_role=role, accepted=accepted)

    # §8.5 requireEmitter
    emitter = document.get("emitter") if isinstance(document.get("emitter"), dict) else {}
    if cfg.require_emitter is not None and emitter.get("name") != cfg.require_emitter:
        return _fail(
            "emitter_name",
            got=emitter.get("name"),
            expected=cfg.require_emitter,
        )

    # Reference metadata must match resolved document (§7.3)
    if binding.get("mode") == "reference":
        ref_emitter = binding.get("emitter") or {}
        for k in ("name", "version", "key_id"):
            if ref_emitter.get(k) != emitter.get(k):
                return _fail(
                    "emitter_name",
                    detail="reference_emitter_mismatch",
                    field=k,
                    got=ref_emitter.get(k),
                    expected=emitter.get(k),
                )

    # §8.6 maxAgeSeconds
    if cfg.max_age_seconds is not None:
        observed = _parse_observed_at(document.get("observed_at"))
        if observed is None:
            return _fail("expired", detail="unparseable_observed_at")
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=timezone.utc)
        age = (clock.astimezone(timezone.utc) - observed).total_seconds()
        if age > cfg.max_age_seconds:
            return _fail(
                "expired",
                age_seconds=age,
                max_age_seconds=cfg.max_age_seconds,
            )

    # §8.7 minLayers
    min_layers = cfg.effective_min_layers()
    layers = document.get("layers") if isinstance(document.get("layers"), dict) else {}
    for layer, required in min_layers.items():
        got = layers.get(layer)
        if not layer_satisfies(got, required):
            return _fail(
                "min_layers",
                layer=layer,
                required=required,
                got=got,
            )

    # §8.8 reference payload_hash
    if binding.get("mode") == "reference":
        binding_hash = binding.get("payload_hash")
        doc_hash = document.get("payload_hash")
        if binding_hash != doc_hash:
            return _fail(
                "hash_mismatch",
                binding_hash=binding_hash,
                document_hash=doc_hash,
            )

    return _ok(
        claim=verify.get("claim"),
        toa_id=verify.get("toa_id"),
        layers=verify.get("layers"),
        emitter_role=role,
        mode=binding.get("mode"),
    )


def load_conformance_public_key(
    fixtures_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Load the packaged toa-conformance test-v1 public key."""
    root = Path(fixtures_dir) if fixtures_dir else (
        Path(__file__).resolve().parents[2]
        / "mcp-extension"
        / "conformance"
        / "fixtures"
    )
    path = root / "keys" / "toa-conformance-test-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))
