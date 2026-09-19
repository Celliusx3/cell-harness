"""The configured MCP servers, connected at startup, and the tools they contribute."""

from __future__ import annotations

import asyncio

from mcp.types import CallToolResult, ReadResourceResult, Tool

from harness.config.sections import McpServer
from harness.mcp.client import ClientFactory, open_client
from harness.mcp.connection import Connection, ServerStatus
from harness.mcp.errors import McpNotConnectedError
from harness.tools.definition import ToolDefinition


class McpServerStore:
    """The live connections to the configured servers, and their tools."""

    def __init__(
        self,
        servers: dict[str, McpServer],
        *,
        client_factory: ClientFactory = open_client,
    ) -> None:
        self._servers = servers
        self._factory = client_factory
        self._connections: dict[str, Connection] = {}

    def tools(self) -> list[ToolDefinition[dict]]:
        """Every tool on offer right now — **the registry provider**."""
        return [tool for connection in self._connections.values() for tool in connection.tools]

    def published(self, server_id: str) -> tuple[Tool, ...]:
        """One server's tools as it published them. `KeyError` if not configured."""
        return self._connection(server_id).published

    async def call(self, server_id: str, name: str, arguments: dict) -> CallToolResult:
        """One `tools/call` on one server, answered verbatim, proxied for an MCP App."""
        return await self._connection(server_id).call(name, arguments)

    async def read_resource(self, server_id: str, uri: str) -> ReadResourceResult:
        """One `resources/read` on one server — the browser fetching an app's HTML."""
        return await self._connection(server_id).read_resource(uri)

    def _connection(self, server_id: str) -> Connection:
        """The connection for a configured server; `KeyError` for one that is not."""
        if server_id not in self._servers:
            raise KeyError(server_id)
        if server_id not in self._connections:
            raise McpNotConnectedError(f"{server_id} is not connected")
        return self._connections[server_id]

    async def start(self) -> None:
        """Connect every configured server, without blocking startup on any."""
        for server_id, server in self._servers.items():
            connection = Connection(id=server_id, server=server, factory=self._factory)
            self._connections[server_id] = connection
            connection.start()

    async def aclose(self) -> None:
        await asyncio.gather(
            *(connection.aclose() for connection in self._connections.values()),
            return_exceptions=True,
        )
        self._connections.clear()

    def statuses(self) -> list[ServerStatus]:
        """Every configured server and whether it came up. For logs and tests."""
        return [
            self._connections[server_id].snapshot()
            if server_id in self._connections
            else ServerStatus(id=server_id, status="disconnected", error="", tool_names=())
            for server_id in self._servers
        ]
