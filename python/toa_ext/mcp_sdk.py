"""
MCP Python SDK reference extension for `dev.agentstatus/toa`.

Uses the official `mcp` package (v2+) Extension intercept to attach signed
AttestationBinding objects onto tools/call results when client require /
server attach policy says so.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from mcp.server.extension import CallNext, Extension
from mcp.server.context import ServerRequestContext
from mcp.types import CallToolRequestParams, CallToolResult

from toa_verify.sign import sign_document

from .attach import (
    build_claim,
    embedded_binding,
    should_attach,
)
from .binding import EXTENSION_ID, ClientSettings

PASS_LAYERS = {
    "reach": "pass",
    "invoke": "pass",
    "functional": "pass",
    "shape": "n/a",
    "openapi_fidelity": "n/a",
    "compositional": "n/a",
}


def _client_toa_settings(ctx: ServerRequestContext[Any, Any]) -> Optional[ClientSettings]:
    meta = ctx.meta or {}
    caps = meta.get("io.modelcontextprotocol/clientCapabilities") or {}
    if not isinstance(caps, Mapping):
        return None
    extensions = caps.get("extensions") or {}
    if not isinstance(extensions, Mapping):
        return None
    raw = extensions.get(EXTENSION_ID)
    if not isinstance(raw, Mapping):
        return None
    roles = raw.get("acceptedEmitterRoles")
    if not isinstance(roles, list):
        roles = ["third_party", "observer"]
    return ClientSettings(
        require=bool(raw.get("require", False)),
        accepted_emitter_roles=[str(r) for r in roles],
        require_emitter=raw.get("requireEmitter"),
        max_age_seconds=raw.get("maxAgeSeconds", 604800),
        min_layers=raw.get("minLayers"),
    )


class ToaAttachExtension(Extension):
    """
    Reference server extension: advertise TOA and attach embedded bindings.

    For conformance / E2E. Production AgentStatus emit stays on the product API;
    this signs with a caller-supplied private key (typically the conformance
    test key).
    """

    identifier = EXTENSION_ID

    def __init__(
        self,
        *,
        private_key: Any,
        public_key_id: str = "test-v1",
        emitter_name: str = "toa-conformance",
        emitter_version: str = "0.1.0",
        emitter_role: str = "third_party",
        server_id: str = "toa-sdk-e2e",
        attach: str = "on_require",
        supported_emitter_roles: Optional[Sequence[str]] = None,
        agent_id: str = "00000000-0000-0000-0000-0000000000e2",
        layers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._private_key = private_key
        self._public_key_id = public_key_id
        self._emitter_name = emitter_name
        self._emitter_version = emitter_version
        self._emitter_role = emitter_role
        self._server_id = server_id
        self._attach = attach
        self._supported_emitter_roles = list(
            supported_emitter_roles or ["third_party", "observer", "server"]
        )
        self._agent_id = agent_id
        self._layers = dict(layers or PASS_LAYERS)

    def settings(self) -> dict[str, Any]:
        return {
            "supportedEmitterRoles": self._supported_emitter_roles,
            "attach": self._attach,
        }

    async def intercept_tool_call(
        self,
        params: CallToolRequestParams,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> CallToolResult:
        result = await call_next(ctx)
        if not isinstance(result, CallToolResult):
            return result

        client = _client_toa_settings(ctx)
        if not should_attach(server_attach=self._attach, client_settings=client):
            return result

        claim = build_claim(
            tool_name=params.name,
            server_id=self._server_id,
            decision_id=f"e2e-{params.name}",
            agent_id=self._agent_id,
            layers=self._layers,
            emitter_name=self._emitter_name,
            emitter_version=self._emitter_version,
            emitter_key_id=self._public_key_id,
            reasons=["mcp-sdk-e2e-attach"],
        )
        document = sign_document(
            claim,
            private_key=self._private_key,
            public_key_id=self._public_key_id,
        )
        binding = embedded_binding(document, emitter_role=self._emitter_role)
        meta = dict(result.meta or {})
        meta[EXTENSION_ID] = binding
        return result.model_copy(update={"meta": meta})


def default_conformance_private_key() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "mcp-extension"
        / "conformance"
        / "fixtures"
        / "keys"
        / "toa-conformance-test-v1.private.json"
    )


def default_conformance_public_key() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "mcp-extension"
        / "conformance"
        / "fixtures"
        / "keys"
        / "toa-conformance-test-v1.json"
    )
