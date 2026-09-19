"""What this package needs of an MCP session, and the real one."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from mcp import Client, StdioServerParameters
from mcp.client.extension import advertise
from mcp.server.apps import APP_MIME_TYPE, EXTENSION_ID
from mcp.types import CallToolResult, ListToolsResult, ReadResourceResult

from harness.config.sections import McpServer


class ClientLike(Protocol):
    """What this package needs of an MCP session."""

    async def list_tools(self, *, cursor: str | None = None) -> ListToolsResult: ...

    async def call_tool(self, name: str, arguments: dict) -> CallToolResult: ...

    async def read_resource(self, uri: str) -> ReadResourceResult: ...


ClientFactory = Callable[[McpServer], AbstractAsyncContextManager[ClientLike]]


def open_client(server: McpServer) -> AbstractAsyncContextManager[ClientLike]:
    """A real stdio session for one configured server."""
    return Client(
        StdioServerParameters(
            command=server.command,
            args=list(server.args),
            # The MCP SDK merges a mapping onto its safe defaults; `{}` would strip `PATH`.
            env=dict(server.env) or None,
        ),
        extensions=[advertise(EXTENSION_ID, {"mimeTypes": [APP_MIME_TYPE]})],
    )
