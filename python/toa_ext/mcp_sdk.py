"""
MCP Python SDK reference extension for `dev.agentstatus/toa`.

Uses the official `mcp` package (v2+) Extension intercept to attach signed
AttestationBinding objects onto tools/call results when client require /
server attach policy says so — including failure / isError paths (§14).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from mcp.server.extension import CallNext, Extension
from mcp.server.context import ServerRequestContext
from mcp.types import CallToolRequestParams, CallToolResult

from toa_verify.sign import sign_document
from toa_verify.verify import args_hash_for

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

FAIL_LAYERS = {
    "reach": "pass",
    "invoke": "pass",
    "functional": "fail",
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
        require_args_hash=bool(raw.get("requireArgsHash", False)),
    )


def _arguments_mapping(params: CallToolRequestParams) -> Mapping[str, Any]:
    raw = getattr(params, "arguments", None)
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _result_is_negative(result: CallToolResult) -> bool:
    if bool(getattr(result, "is_error", False) or getattr(result, "isError", False)):
        return True
    # Soft-fail style structured content used in conformance / demos.
    structured = getattr(result, "structured_content", None) or getattr(
        result, "structuredContent", None
    )
    if isinstance(structured, Mapping) and structured.get("functional") == "fail":
        return True
    return False


class ToaAttachExtension(Extension):
    """
    Reference server extension: advertise TOA and attach embedded bindings.

    For conformance / E2E. Production AgentStatus emit stays on the product API;
    this signs with a caller-supplied private key (typically the conformance
    test key).

    When attach policy fires, MUST attach on success and on failure / isError
    paths, with ``disposition`` set accordingly (§14).
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
        fail_layers: Optional[Mapping[str, str]] = None,
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
        self._fail_layers = dict(fail_layers or FAIL_LAYERS)

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

        negative = _result_is_negative(result)
        disposition = "failed" if negative else "delivered"
        layers = self._fail_layers if negative else self._layers
        reasons = (
            ["mcp-sdk-e2e-attach-negative"]
            if negative
            else ["mcp-sdk-e2e-attach"]
        )
        # Always bind call args (digest only). Closes substitution when client
        # recomputes expected_args_hash / sets requireArgsHash.
        digest = args_hash_for(_arguments_mapping(params))

        claim = build_claim(
            tool_name=params.name,
            server_id=self._server_id,
            decision_id=f"e2e-{params.name}",
            agent_id=self._agent_id,
            layers=layers,
            emitter_name=self._emitter_name,
            emitter_version=self._emitter_version,
            emitter_key_id=self._public_key_id,
            reasons=reasons,
            disposition=disposition,
            args_hash=digest,
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
