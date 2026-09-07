"""Shared result / settings types for the harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class ClientToaSettings:
    require: bool = False
    accepted_emitter_roles: Sequence[str] = ("third_party", "observer")
    require_emitter: Optional[str] = None
    max_age_seconds: Optional[int] = 604800
    min_layers: Optional[Mapping[str, str]] = None
    require_args_hash: bool = False
    expected_args_hash: Optional[str] = None

    def to_capability(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "require": self.require,
            "acceptedEmitterRoles": list(self.accepted_emitter_roles),
            "requireEmitter": self.require_emitter,
            "maxAgeSeconds": self.max_age_seconds,
            "requireArgsHash": self.require_args_hash,
        }
        if self.min_layers is not None:
            out["minLayers"] = dict(self.min_layers)
        elif self.require:
            from .constants import DEFAULT_MIN_LAYERS_WHEN_REQUIRE

            out["minLayers"] = dict(DEFAULT_MIN_LAYERS_WHEN_REQUIRE)
        return out


@dataclass(frozen=True)
class ServerToaSettings:
    supported_emitter_roles: Sequence[str] = ("third_party", "observer", "server")
    attach: str = "on_require"

    def to_capability(self) -> Dict[str, Any]:
        return {
            "supportedEmitterRoles": list(self.supported_emitter_roles),
            "attach": self.attach,
        }


@dataclass
class ToolCallResult:
    """Minimal MCP tools/call success result shape."""

    content: List[Dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    _meta: Dict[str, Any] = field(default_factory=dict)
    structured_content: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "content": self.content,
            "isError": self.is_error,
        }
        if self._meta:
            out["_meta"] = self._meta
        if self.structured_content is not None:
            out["structuredContent"] = self.structured_content
        return out


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    name: str
    status: Status
    reason: str
    detail: Optional[str] = None
    checks: Mapping[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "status": self.status.value,
            "reason": self.reason,
            "detail": self.detail,
            "checks": dict(self.checks),
        }
