"""The saved MCP servers, started once their keys are found, and their tools."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

from mcp.types import CallToolResult, ReadResourceResult
from mcp.types import Tool as McpTool

from harness.config.sections import McpServer
from harness.mcp._connection import Connection
from harness.mcp.client import McpClientFactory
from harness.mcp.clients.stdio import open_stdio_client
from harness.mcp.keys import missing_keys
from harness.mcp.models.errors import McpNotConnectedError, McpServerNotFound, McpServerTaken
from harness.mcp.models.status import ServerStatus
from harness.mcp.tool import can_write, namespaced
from harness.tools import Tool


class McpService:
    """The live connections to the saved servers, those waiting, and their tools."""

    def __init__(
        self,
        servers: Mapping[str, McpServer],
        *,
        client_factory: McpClientFactory = open_stdio_client,
    ) -> None:
        self._servers: Mapping[str, McpServer] = dict(servers)
        self._factory = client_factory
        self._connections: dict[str, Connection] = {}
        self._changing = asyncio.Lock()

    def tools(self) -> list[Tool[dict]]:
        """Every tool on offer right now — **the registry provider**."""
        return [tool for connection in self._connections.values() for tool in connection.tools]

    def instructions(self) -> dict[str, str]:
        """Each connected server's non-empty instructions, by server id, in config order."""
        return {
            server_id: connection.instructions
            for server_id, connection in self._connections.items()
            if connection.status == "connected" and connection.instructions
        }

    def writing_tool_names(self) -> frozenset[str]:
        """Every tool on offer right now that may change something, as the model calls it."""
        offered = {tool.name for tool in self.tools()}
        return frozenset(
            tool_name
            for connection in self._connections.values()
            for tool in connection.published
            if can_write(tool) and (tool_name := namespaced(connection.id, tool.name)) in offered
        )

    def server(self, server_id: str) -> McpServer:
        """How `server_id` is run, its keys in its env. `KeyError` if not configured."""
        return self._servers[server_id]

    def published(self, server_id: str) -> tuple[McpTool, ...]:
        """One server's tools as it published them. `KeyError` if not configured."""
        return self._connection(server_id).published

    async def call(self, server_id: str, server_tool_name: str, arguments: dict) -> CallToolResult:
        """One `tools/call` on one server, answered verbatim, proxied for an MCP App."""
        return await self._connection(server_id).call(server_tool_name, arguments)

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
        """Start every server whose keys are found, waiting for none of them to connect."""
        async with self._changing:
            for server_id in self._servers:
                await self._open(server_id)

    async def restart(self, server_id: str) -> None:
        """Close `server_id`, then open it again. `KeyError` if unknown."""
        if server_id not in self._servers:
            raise KeyError(server_id)
        async with self._changing:
            running = self._connections.get(server_id)
            if running is not None:
                await running.aclose()
            await self._open(server_id)

    async def add(self, server_id: str, server: McpServer) -> None:
        """Serve `server` as `server_id` and start it; `McpServerTaken` if the id is served."""
        async with self._changing:
            if server_id in self._servers:
                raise McpServerTaken(f"a server is already named {server_id!r}")
            self._servers = {**self._servers, server_id: server}
            await self._open(server_id)

    async def change(self, server_id: str, server: McpServer) -> None:
        """Close the server `server_id`, then start it again as `server`."""
        async with self._changing:
            self._refuse_unless_served(server_id)
            await self._close(server_id)
            self._servers = {**self._servers, server_id: server}
            await self._open(server_id)

    async def remove(self, server_id: str) -> None:
        """Close the server `server_id` and forget it, its tools with it."""
        async with self._changing:
            self._refuse_unless_served(server_id)
            await self._close(server_id)
            self._servers = {key: kept for key, kept in self._servers.items() if key != server_id}

    def _refuse_unless_served(self, server_id: str) -> None:
        if server_id not in self._servers:
            raise McpServerNotFound(f"no MCP server {server_id!r}")

    async def _close(self, server_id: str) -> None:
        running = self._connections.pop(server_id, None)
        if running is not None:
            await running.aclose()

    async def _open(self, server_id: str) -> None:
        """Start `server_id` with its env, or leave it waiting for a key that env lacks."""
        server = self._servers[server_id]
        connection = Connection(id=server_id, server=server, factory=self._factory)
        self._connections[server_id] = connection
        missing = missing_keys(server)
        if missing:
            connection.wait_for(missing)
        else:
            connection.start()

    async def aclose(self) -> None:
        async with self._changing:
            await asyncio.gather(
                *(connection.aclose() for connection in self._connections.values()),
                return_exceptions=True,
            )
            self._connections.clear()

    def statuses(self) -> list[ServerStatus]:
        """Every configured server: whether it came up, or the keys it waits for."""
        return [
            self._connections[server_id].snapshot()
            if server_id in self._connections
            else ServerStatus(id=server_id, status="disconnected", error="", tool_names=())
            for server_id in self._servers
        ]
