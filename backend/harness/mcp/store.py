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
    """The live connections to the configured servers, and their tools.

    **No add or remove.** Servers are configuration — `settings.mcp.servers` —
    so the catalog has one source and changing it is editing `config.json`.
    A second, runtime store would make "which servers are configured?" two
    questions with two answers.
    """

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
        """Every tool on offer right now — **the registry provider**.

        Synchronous and snapshot-reading, because the registry calls it on every
        turn. A server still connecting contributes nothing and then contributes
        its tools, without anyone rebuilding the agent.
        """
        return [tool for connection in self._connections.values() for tool in connection.tools]

    def published(self, server_id: str) -> tuple[Tool, ...]:
        """One server's tools as it published them. `KeyError` if not configured."""
        return self._connection(server_id).published

    async def call(self, server_id: str, name: str, arguments: dict) -> CallToolResult:
        """One `tools/call` on one server, by the server's own name, answered
        verbatim — the harness proxying for an MCP App, which is not the model
        and gets the result as its server sent it."""
        return await self._connection(server_id).call(name, arguments)

    async def read_resource(self, server_id: str, uri: str) -> ReadResourceResult:
        """One `resources/read` on one server — the browser fetching an app's HTML."""
        return await self._connection(server_id).read_resource(uri)

    def _connection(self, server_id: str) -> Connection:
        """`KeyError` for a server that is not configured: that is the caller
        naming something that does not exist, distinct from one that is
        configured and down, which the connection reports as not connected."""
        if server_id not in self._servers:
            raise KeyError(server_id)
        if server_id not in self._connections:
            raise McpNotConnectedError(f"{server_id} is not connected")
        return self._connections[server_id]

    async def start(self) -> None:
        """Connect every configured server, without blocking startup on any.

        Deliberately not awaiting readiness: a server that takes the full command
        timeout to fail would otherwise hold up the whole application, and its
        tools are simply absent from the turns that happen before it answers.
        """
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
