"""Binding validation API.

Prefer the real ``toa_ext`` library when installed. Until that lands, use the
local stub which implements wire-spec §8 policy checks and optionally
``toa_verify`` for Ed25519 when cryptography + fixtures are available.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence

from .constants import (
    DEFAULT_ACCEPTED_EMITTER_ROLES,
    DEFAULT_MAX_AGE_SECONDS,
    DEFAULT_MIN_LAYERS_WHEN_REQUIRE,
    EMITTER_ROLES,
    EXTENSION_ID,
    TOA_SPEC,
)
from .types import ClientToaSettings


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str
    detail: Optional[str] = None
    backend: str = "stub"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "detail": self.detail,
            "backend": self.backend,
        }


def _layer_satisfies(actual: Optional[str], required: str) -> bool:
    if actual is None or actual == "n/a":
        return False
    if required == "pass":
        return actual == "pass"
    if required == "warn":
        return actual in ("pass", "warn")
    return False


def _parse_observed_at(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_document(
    binding: Mapping[str, Any],
    *,
    document_store: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    mode = binding.get("mode")
    if mode == "embedded":
        doc = binding.get("document")
        if not isinstance(doc, Mapping):
            return None, "missing_document"
        return dict(doc), None
    if mode == "reference":
        uri = binding.get("uri")
        if not isinstance(uri, str) or not uri:
            return None, "missing_uri"
        store = document_store or {}
        doc = store.get(uri)
        if doc is None:
            return None, "unresolved_reference"
        return dict(doc), None
    return None, "bad_mode"


def _verify_signature(
    document: Mapping[str, Any],
    *,
    public_key: Any = None,
    require_emitter: Optional[str] = None,
) -> ValidationResult:
    """Delegate crypto to toa_verify when available; else soft-fail clearly."""
    try:
        from toa_verify import verify_document  # type: ignore
    except ImportError:
        # Structural harness without toa-verify: cannot prove signatures.
        if document.get("signature"):
            return ValidationResult(
                valid=False,
                reason="crypto_unavailable",
                detail="install toa-verify (or toa_ext) for signature checks",
                backend="stub",
            )
        return ValidationResult(valid=False, reason="missing_signature", backend="stub")

    result = verify_document(
        document,
        public_key=public_key,
        require_emitter=require_emitter,
    )
    if result.get("valid"):
        return ValidationResult(valid=True, reason="ok", backend="toa_verify")
    reason = str(result.get("reason") or "invalid_signature")
    # Normalize emitter mismatch to extension reason code.
    if reason.startswith("emitter_mismatch"):
        return ValidationResult(
            valid=False,
            reason="emitter_name",
            detail=reason,
            backend="toa_verify",
        )
    if reason == "invalid_signature" or reason.startswith("verify_error"):
        return ValidationResult(
            valid=False,
            reason="invalid_signature",
            detail=reason,
            backend="toa_verify",
        )
    return ValidationResult(valid=False, reason=reason, detail=reason, backend="toa_verify")


def _stub_validate_binding(
    binding: Mapping[str, Any],
    *,
    client_settings: ClientToaSettings,
    tool_name: Optional[str] = None,
    public_key: Any = None,
    document_store: Optional[Mapping[str, Mapping[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> ValidationResult:
    """Implement extension §8 validation algorithm (local stub)."""
    if not isinstance(binding, Mapping):
        return ValidationResult(valid=False, reason="missing_binding", backend="stub")

    # §8 order: resolve → spec → signature → emitter_role → requireEmitter → maxAge → minLayers → hash
    if binding.get("spec") != TOA_SPEC:
        return ValidationResult(valid=False, reason="spec_mismatch", backend="stub")

    role = binding.get("emitter_role")
    if role not in EMITTER_ROLES:
        return ValidationResult(valid=False, reason="emitter_role", detail=f"bad_role:{role}", backend="stub")

    document, resolve_err = _resolve_document(binding, document_store=document_store)
    if document is None:
        return ValidationResult(
            valid=False,
            reason="missing_binding" if resolve_err == "missing_document" else (resolve_err or "missing_binding"),
            backend="stub",
        )

    if document.get("spec") != TOA_SPEC:
        return ValidationResult(valid=False, reason="spec_mismatch", backend="stub")

    sig = _verify_signature(
        document,
        public_key=public_key,
        require_emitter=None,  # requireEmitter checked below for stable reason codes
    )
    if not sig.valid:
        # crypto_unavailable is harness-local; scenarios may SKIP until verify deps exist.
        return sig

    accepted = list(client_settings.accepted_emitter_roles or DEFAULT_ACCEPTED_EMITTER_ROLES)
    if role not in accepted:
        return ValidationResult(valid=False, reason="emitter_role", detail=f"rejected:{role}", backend=sig.backend)

    emitter = document.get("emitter") if isinstance(document.get("emitter"), Mapping) else {}
    if client_settings.require_emitter is not None:
        if emitter.get("name") != client_settings.require_emitter:
            return ValidationResult(
                valid=False,
                reason="emitter_name",
                detail=f"got:{emitter.get('name')}",
                backend=sig.backend,
            )

    max_age = client_settings.max_age_seconds
    if max_age is None:
        max_age = DEFAULT_MAX_AGE_SECONDS
    if max_age is not None:
        observed = _parse_observed_at(document.get("observed_at"))
        if observed is None:
            return ValidationResult(valid=False, reason="expired", detail="bad_observed_at", backend=sig.backend)
        ref = now or datetime.now(timezone.utc)
        age = (ref - observed).total_seconds()
        if age > float(max_age) or age < -60:
            return ValidationResult(
                valid=False,
                reason="expired",
                detail=f"age_seconds:{int(age)}",
                backend=sig.backend,
            )

    min_layers = client_settings.min_layers
    if min_layers is None and client_settings.require:
        min_layers = DEFAULT_MIN_LAYERS_WHEN_REQUIRE
    if min_layers:
        layers = document.get("layers") if isinstance(document.get("layers"), Mapping) else {}
        for layer, required in min_layers.items():
            actual = layers.get(layer)
            if not _layer_satisfies(actual if isinstance(actual, str) else None, required):
                return ValidationResult(
                    valid=False,
                    reason="min_layers",
                    detail=f"{layer}:{actual}<{required}",
                    backend=sig.backend,
                )

    if binding.get("mode") == "reference":
        expected_hash = binding.get("payload_hash")
        actual_hash = document.get("payload_hash")
        if expected_hash != actual_hash:
            return ValidationResult(
                valid=False,
                reason="hash_mismatch",
                detail=f"binding:{expected_hash} doc:{actual_hash}",
                backend=sig.backend,
            )
        bind_emitter = binding.get("emitter") if isinstance(binding.get("emitter"), Mapping) else {}
        if bind_emitter and (
            bind_emitter.get("name") != emitter.get("name")
            or bind_emitter.get("key_id") != emitter.get("key_id")
        ):
            return ValidationResult(
                valid=False,
                reason="emitter_name",
                detail="reference_emitter_mismatch",
                backend=sig.backend,
            )

    if tool_name is not None:
        tool = document.get("tool") if isinstance(document.get("tool"), Mapping) else {}
        if tool.get("name") != tool_name:
            return ValidationResult(
                valid=False,
                reason="wrong_tool",
                detail=f"expected:{tool_name} got:{tool.get('name')}",
                backend=sig.backend,
            )

    return ValidationResult(valid=True, reason="ok", backend=sig.backend)


def _try_toa_ext_validate(
    binding: Mapping[str, Any],
    *,
    client_settings: ClientToaSettings,
    tool_name: Optional[str] = None,
    public_key: Any = None,
    document_store: Optional[Mapping[str, Mapping[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> Optional[ValidationResult]:
    """Call ``toa_ext.validate_binding`` when the library is importable."""
    try:
        from toa_ext import ClientSettings, validate_binding as ext_validate  # type: ignore
    except ImportError:
        return None

    settings = ClientSettings(
        require=client_settings.require,
        accepted_emitter_roles=list(client_settings.accepted_emitter_roles),
        require_emitter=client_settings.require_emitter,
        max_age_seconds=client_settings.max_age_seconds,
        min_layers=dict(client_settings.min_layers)
        if client_settings.min_layers is not None
        else None,
    )
    try:
        raw = ext_validate(
            binding,
            settings=settings,
            public_key=public_key,
            document_store=document_store,
            now=now,
        )
    except TypeError:
        return None

    if not isinstance(raw, Mapping):
        return None

    reason = str(raw.get("reason") or ("ok" if raw.get("valid") else "invalid"))
    detail = raw.get("detail")
    if detail is None and reason != "ok":
        # Prefer a compact extra field for harness diagnostics.
        for k in ("verify_reason", "got", "layer", "emitter_role"):
            if k in raw:
                detail = f"{k}={raw[k]}"
                break

    # Optional tool.name correlation is harness-side (spec §9.4); toa_ext may omit it.
    if raw.get("valid") and tool_name is not None:
        claim = raw.get("claim") if isinstance(raw.get("claim"), Mapping) else {}
        tool = claim.get("tool") if isinstance(claim.get("tool"), Mapping) else {}
        # Fallback: peek embedded/reference document via binding.
        if not tool and binding.get("mode") == "embedded":
            doc = binding.get("document") if isinstance(binding.get("document"), Mapping) else {}
            tool = doc.get("tool") if isinstance(doc.get("tool"), Mapping) else {}
        if tool.get("name") != tool_name:
            return ValidationResult(
                valid=False,
                reason="wrong_tool",
                detail=f"expected:{tool_name} got:{tool.get('name')}",
                backend="toa_ext",
            )

    return ValidationResult(
        valid=bool(raw.get("valid")),
        reason=reason,
        detail=str(detail) if detail is not None else None,
        backend="toa_ext",
    )


def validate_binding(
    binding: Optional[Mapping[str, Any]],
    *,
    client_settings: Optional[ClientToaSettings] = None,
    tool_name: Optional[str] = None,
    public_key: Any = None,
    document_store: Optional[Mapping[str, Mapping[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> ValidationResult:
    """Public validate entrypoint used by scenarios and FakeMcpClient."""
    if binding is None:
        return ValidationResult(valid=False, reason="missing_binding", backend="harness")

    settings = client_settings or ClientToaSettings(require=True)

    ext = _try_toa_ext_validate(
        binding,
        client_settings=settings,
        tool_name=tool_name,
        public_key=public_key,
        document_store=document_store,
        now=now,
    )
    if ext is not None:
        return ext

    return _stub_validate_binding(
        binding,
        client_settings=settings,
        tool_name=tool_name,
        public_key=public_key,
        document_store=document_store,
        now=now,
    )


def evaluate_tools_call(
    *,
    result: Mapping[str, Any],
    tool_name: str,
    client_settings: Optional[ClientToaSettings],
    public_key: Any = None,
    document_store: Optional[Mapping[str, Mapping[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Apply client require policy to a tools/call result."""
    if client_settings is None:
        return {
            "rpc": dict(result),
            "toa_ok": None,
            "toa_reason": "not_required",
            "binding": None,
        }

    meta = result.get("_meta") if isinstance(result.get("_meta"), Mapping) else {}
    binding = meta.get(EXTENSION_ID)

    if not client_settings.require:
        if binding is None:
            return {
                "rpc": dict(result),
                "toa_ok": True,
                "toa_reason": "optional_absent",
                "binding": None,
            }
        # Optional: invalid bindings should not fail the call at protocol layer.
        vr = validate_binding(
            binding if isinstance(binding, Mapping) else None,
            client_settings=client_settings,
            tool_name=tool_name,
            public_key=public_key,
            document_store=document_store,
            now=now,
        )
        return {
            "rpc": dict(result),
            "toa_ok": True,
            "toa_reason": "optional_" + ("valid" if vr.valid else f"ignored:{vr.reason}"),
            "binding": binding,
            "validation": vr.as_dict(),
        }

    if binding is None or not isinstance(binding, Mapping):
        return {
            "rpc": dict(result),
            "toa_ok": False,
            "toa_reason": "missing_binding",
            "binding": None,
        }

    vr = validate_binding(
        binding,
        client_settings=client_settings,
        tool_name=tool_name,
        public_key=public_key,
        document_store=document_store,
        now=now,
    )
    return {
        "rpc": dict(result),
        "toa_ok": vr.valid,
        "toa_reason": vr.reason if not vr.valid else "ok",
        "binding": binding,
        "validation": vr.as_dict(),
    }


def parse_server_toa_settings(raw: Any) -> tuple[bool, str, Dict[str, Any]]:
    """Validate server capability settings shape. Returns (ok, reason, normalized)."""
    from .constants import ATTACH_MODES

    if not isinstance(raw, Mapping):
        return False, "settings_not_object", {}

    normalized: Dict[str, Any] = {}
    attach = raw.get("attach", "on_require")
    if attach not in ATTACH_MODES:
        return False, f"invalid_attach:{attach}", {}
    normalized["attach"] = attach

    roles = raw.get("supportedEmitterRoles", ["third_party", "observer", "server"])
    if not isinstance(roles, Sequence) or isinstance(roles, (str, bytes)):
        return False, "invalid_supportedEmitterRoles", {}
    bad = [r for r in roles if r not in EMITTER_ROLES]
    if bad:
        return False, f"invalid_role:{bad[0]}", {}
    normalized["supportedEmitterRoles"] = list(roles)

    # Unknown fields ignored (do not fail).
    return True, "ok", normalized
