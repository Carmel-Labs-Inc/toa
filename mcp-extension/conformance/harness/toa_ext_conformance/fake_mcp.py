"""In-process fake MCP client/server for extension negotiation + tools/call.

No network. Capability advertisement and tool results are fully controllable so
scenarios can exercise attach / require / degrade without a real MCP transport.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping, Optional

from .constants import EXTENSION_ID
from .types import ClientToaSettings, ServerToaSettings, ToolCallResult

BindingFactory = Callable[[str, Mapping[str, Any], ClientToaSettings], Optional[Dict[str, Any]]]


class FakeMcpServer:
    """Minimal server: initialize capabilities + echo / soft_fail tools."""

    def __init__(
        self,
        *,
        toa: Optional[ServerToaSettings] = None,
        advertise_toa: bool = True,
        # Mis-advertise under wrong key for T1 negative checks.
        wrong_key_toa: bool = False,
        binding_factory: Optional[BindingFactory] = None,
        force_no_binding: bool = False,
        extra_extensions: Optional[Mapping[str, Any]] = None,
    ):
        self.toa = toa or ServerToaSettings()
        self.advertise_toa = advertise_toa
        self.wrong_key_toa = wrong_key_toa
        self.binding_factory = binding_factory
        self.force_no_binding = force_no_binding
        self.extra_extensions = dict(extra_extensions or {})
        self._client_settings: Optional[ClientToaSettings] = None

    def set_peer_client_settings(self, settings: Optional[ClientToaSettings]) -> None:
        self._client_settings = settings

    def initialize_result(self) -> Dict[str, Any]:
        capabilities: Dict[str, Any] = {"tools": {"listChanged": False}}
        extensions: Dict[str, Any] = dict(self.extra_extensions)

        if self.advertise_toa and not self.wrong_key_toa:
            extensions[EXTENSION_ID] = self.toa.to_capability()

        if extensions:
            capabilities["extensions"] = extensions

        # Deliberate incorrect placement used by T1 to assert MUST NOT.
        if self.wrong_key_toa:
            capabilities["toa"] = self.toa.to_capability()

        return {
            "protocolVersion": "2025-06-18",
            "capabilities": capabilities,
            "serverInfo": {"name": "toa-conformance-fake", "version": "0.1.0"},
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "echo",
                "description": "Sync echo; returns {text: input}",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            {
                "name": "soft_fail",
                "description": "RPC success with soft-error style content",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    def call_tool(self, name: str, arguments: Optional[Mapping[str, Any]] = None) -> ToolCallResult:
        arguments = dict(arguments or {})
        if name == "echo":
            text = arguments.get("text", "")
            result = ToolCallResult(
                content=[{"type": "text", "text": str(text)}],
                structured_content={"text": text},
            )
        elif name == "soft_fail":
            result = ToolCallResult(
                content=[{"type": "text", "text": ""}],
                is_error=False,
                structured_content={"functional": "fail"},
            )
        else:
            raise KeyError(f"unknown tool: {name}")

        if self.force_no_binding:
            return result

        should_attach = self._should_attach()
        if should_attach and self.binding_factory is not None:
            client = self._client_settings or ClientToaSettings()
            binding = self.binding_factory(name, arguments, client)
            if binding is not None:
                result._meta[EXTENSION_ID] = deepcopy(binding)
        return result

    def _should_attach(self) -> bool:
        if not self.advertise_toa or self.wrong_key_toa:
            return False
        attach = self.toa.attach
        if attach == "never":
            return False
        if attach == "always":
            return True
        # on_require
        client = self._client_settings
        return bool(client and client.require)


class FakeMcpClient:
    """Minimal client: advertises TOA settings and evaluates tools/call results."""

    def __init__(
        self,
        *,
        toa: Optional[ClientToaSettings] = None,
        advertise_toa: bool = True,
        server_id: str = "toa-conformance-fake",
        pinned_public_key_id: Optional[str] = None,
        pinned_key_fingerprint: Optional[str] = None,
        pinned_emitter_name: Optional[str] = None,
        transport: Optional[str] = None,
        revocation_policy: Optional[str] = None,
    ):
        self.toa = toa
        self.advertise_toa = advertise_toa and toa is not None
        self.server_id = server_id
        self.pinned_public_key_id = pinned_public_key_id
        self.pinned_key_fingerprint = pinned_key_fingerprint
        self.pinned_emitter_name = pinned_emitter_name
        self.transport = transport
        self.revocation_policy = revocation_policy
        self.server_capabilities: Dict[str, Any] = {}
        self.negotiation_record: Optional[Dict[str, Any]] = None

    def client_capabilities(self) -> Dict[str, Any]:
        caps: Dict[str, Any] = {}
        if self.advertise_toa and self.toa is not None:
            caps["extensions"] = {EXTENSION_ID: self.toa.to_capability()}
        return caps

    def connect(self, server: FakeMcpServer) -> Dict[str, Any]:
        init = server.initialize_result()
        self.server_capabilities = init.get("capabilities") or {}
        if self.advertise_toa:
            server.set_peer_client_settings(self.toa)
        else:
            server.set_peer_client_settings(None)
        # §13: persist NegotiationRecord at capability exchange.
        from toa_ext.negotiation import negotiation_from_initialize

        client_cap = None
        if self.toa is not None:
            client_cap = self.toa.to_capability()
        self.negotiation_record = negotiation_from_initialize(
            init,
            server_id=self.server_id,
            client_settings=client_cap,
            pinned_public_key_id=self.pinned_public_key_id,
            pinned_key_fingerprint=self.pinned_key_fingerprint,
            pinned_emitter_name=self.pinned_emitter_name,
            transport=self.transport,
            revocation_policy=self.revocation_policy,
        )
        return init

    def call_tool(
        self,
        server: FakeMcpServer,
        name: str,
        arguments: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute tools/call and apply client-side TOA require policy.

        Returns a dict with:
          - ``rpc``: core tools/call result dict
          - ``toa_ok``: bool | None (None = TOA not required / not advertised)
          - ``toa_reason``: reason code or ``ok`` / ``not_required``
        """
        from .validate_api import evaluate_tools_call

        raw = server.call_tool(name, arguments)
        return evaluate_tools_call(
            result=raw.to_dict(),
            tool_name=name,
            client_settings=self.toa if self.advertise_toa else None,
        )
