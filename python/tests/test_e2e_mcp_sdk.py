"""
Full E2E against the official MCP Python SDK (v2+).

Not FakeMcp. Real Client + MCPServer, protocol 2026-07-28, extensions via
server/discover + per-request clientCapabilities, tools/call result _meta.
Includes in-process and stdio subprocess transport.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("mcp")
# mcp 2.x is required for Extension + 2026-07-28; pin via optional extra `e2e`.
import importlib.metadata as _md

try:
    _mcp_ver = _md.version("mcp")
except _md.PackageNotFoundError:  # pragma: no cover
    pytest.skip("mcp package not installed", allow_module_level=True)
if tuple(int(p) for p in _mcp_ver.split(".")[:2]) < (2, 1):
    pytest.skip(f"mcp>={2.1} required for E2E, found {_mcp_ver}", allow_module_level=True)

from mcp import Client, StdioServerParameters
from mcp.client.extension import advertise
from mcp.server.mcpserver import MCPServer

from toa_ext import EXTENSION_ID, ClientSettings, enforce_client_require
from toa_ext.mcp_sdk import (
    ToaAttachExtension,
    default_conformance_private_key,
    default_conformance_public_key,
)

PRIV = default_conformance_private_key()
PUB = default_conformance_public_key()
PYTHON_ROOT = Path(__file__).resolve().parents[1]


def _server(*, attach: str = "on_require", with_toa: bool = True) -> MCPServer:
    extensions = []
    if with_toa:
        extensions.append(
            ToaAttachExtension(
                private_key=PRIV,
                public_key_id="test-v1",
                attach=attach,
                supported_emitter_roles=["third_party"],
            )
        )
    server = MCPServer("toa-sdk-e2e", extensions=extensions)

    @server.tool()
    def echo(text: str = "hi") -> str:
        return text

    return server


def _enforce(result, *, require_emitter: str | None = "toa-conformance") -> dict:
    return enforce_client_require(
        {"content": [], "_meta": dict(result.meta or {})},
        client_settings=ClientSettings(
            require=True,
            accepted_emitter_roles=["third_party"],
            require_emitter=require_emitter,
        ),
        public_key=PUB,
        expected_tool_name="echo",
    )


@pytest.mark.asyncio
async def test_e2e_advertise_on_discover():
    async with Client(_server()) as client:
        assert client.server_capabilities is not None
        assert client.server_capabilities.extensions is not None
        assert EXTENSION_ID in client.server_capabilities.extensions
        settings = client.server_capabilities.extensions[EXTENSION_ID]
        assert settings.get("attach") == "on_require"
        # Negotiated modern protocol
        assert str(client.protocol_version) in ("2026-07-28", "ProtocolVersion.V2026_07_28") or "2026-07-28" in str(
            client.protocol_version
        )


@pytest.mark.asyncio
async def test_e2e_attach_when_client_requires():
    client_ext = advertise(
        EXTENSION_ID,
        {
            "require": True,
            "acceptedEmitterRoles": ["third_party"],
            "requireEmitter": "toa-conformance",
        },
    )
    async with Client(_server(attach="on_require"), extensions=[client_ext]) as client:
        result = await client.call_tool("echo", {"text": "hello-e2e"})
        assert result.meta is not None
        assert EXTENSION_ID in result.meta
        binding = result.meta[EXTENSION_ID]
        assert binding["mode"] == "embedded"
        assert binding["emitter_role"] == "third_party"
        assert binding["document"]["tool"]["name"] == "echo"
        enforced = _enforce(result)
        assert enforced["ok"] is True, enforced


@pytest.mark.asyncio
async def test_e2e_no_attach_when_client_does_not_require():
    async with Client(_server(attach="on_require")) as client:
        result = await client.call_tool("echo", {"text": "no-require"})
        assert EXTENSION_ID not in (result.meta or {})


@pytest.mark.asyncio
async def test_e2e_fail_closed_when_require_but_server_never_attaches():
    client_ext = advertise(
        EXTENSION_ID,
        {"require": True, "acceptedEmitterRoles": ["third_party"]},
    )
    async with Client(_server(with_toa=False), extensions=[client_ext]) as client:
        result = await client.call_tool("echo", {"text": "bare"})
        enforced = _enforce(result, require_emitter=None)
        assert enforced["ok"] is False
        assert enforced["error"]["data"]["reason"] == "missing_binding"


@pytest.mark.asyncio
async def test_e2e_stdio_subprocess_roundtrip(tmp_path: Path):
    """Separate OS process over stdio — transport E2E."""
    server_py = tmp_path / "toa_stdio_server.py"
    server_py.write_text(
        f"""
from pathlib import Path
from mcp.server.mcpserver import MCPServer
from toa_ext.mcp_sdk import ToaAttachExtension

server = MCPServer(
    "toa-stdio-e2e",
    extensions=[
        ToaAttachExtension(
            private_key=Path(r"{PRIV}"),
            public_key_id="test-v1",
            attach="on_require",
            supported_emitter_roles=["third_party"],
        )
    ],
)

@server.tool()
def echo(text: str = "hi") -> str:
    return text

if __name__ == "__main__":
    server.run(transport="stdio")
""",
        encoding="utf-8",
    )

    params = StdioServerParameters(
        command="python3.11",
        args=[str(server_py)],
        cwd=str(PYTHON_ROOT),
    )
    client_ext = advertise(
        EXTENSION_ID,
        {
            "require": True,
            "acceptedEmitterRoles": ["third_party"],
            "requireEmitter": "toa-conformance",
        },
    )
    async with Client(params, extensions=[client_ext]) as client:
        assert EXTENSION_ID in (client.server_capabilities.extensions or {})
        result = await client.call_tool("echo", {"text": "stdio-e2e"})
        assert result.meta and EXTENSION_ID in result.meta
        enforced = _enforce(result)
        assert enforced["ok"] is True, enforced
