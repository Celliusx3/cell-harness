"""The built-in and saved MCP servers, started once their keys are found, and their tools."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping

from mcp.types import CallToolResult, ReadResourceResult
from mcp.types import Tool as McpTool

from harness.config.sections import McpServer
from harness.mcp._connection import Connection
from harness.mcp.client import McpClientFactory
from harness.mcp.clients.stdio import open_stdio_client
from harness.mcp.keys import CapabilityKeys, missing_keys, with_saved_keys
from harness.mcp.models.errors import (
    McpNotConnectedError,
    McpServerBuiltIn,
    McpServerNotFound,
    McpServerTaken,
    RequiredServerError,
)
from harness.mcp.models.status import ServerStatus
from harness.mcp.required import required_refusal
from harness.mcp.tool import can_write, namespaced
from harness.tools import Tool

REQUIRED_CONNECT_TIMEOUT_SECONDS = 120.0


class McpService:
    """The live connections to the built-in and saved servers, those waiting, and their tools."""

    def __init__(
        self,
        servers: Mapping[str, McpServer],
        *,
        saved: Mapping[str, McpServer],
        keys: CapabilityKeys,
        client_factory: McpClientFactory = open_stdio_client,
    ) -> None:
        clashes = sorted(set(servers) & set(saved))
        if clashes:
            raise McpServerTaken(
                f"{', '.join(clashes)} is both built in and saved; remove the saved one"
            )
        self._built_in_ids = frozenset(servers)
        self._servers: Mapping[str, McpServer] = {**servers, **saved}
        self._keys = keys
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

    def needs(self, server_id: str) -> tuple[str, ...]:
        """The env keys `server_id` waits for until they are found. `KeyError` if not configured."""
        return self._servers[server_id].needs

    def server(self, server_id: str) -> McpServer:
        """How `server_id` is run, without its saved keys. `KeyError` if not configured."""
        return self._servers[server_id]

    def is_built_in(self, server_id: str) -> bool:
        """Whether `server_id` comes from config rather than the person's saved servers."""
        return server_id in self._built_in_ids

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
        """Connect every server whose keys are found; wait only for the required, refuse without."""
        async with self._changing:
            for server_id in self._servers:
                await self._open(server_id)
        refusal = await self._required_refusal()
        if refusal is not None:
            await self.aclose()
            raise RequiredServerError(refusal)

    async def restart(self, server_id: str) -> None:
        """Close `server_id`, then open it again with the keys found now. `KeyError` if unknown."""
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
        """Close the saved server `server_id`, then start it again as `server`."""
        async with self._changing:
            self._refuse_unless_saved(server_id)
            await self._close(server_id)
            self._servers = {**self._servers, server_id: server}
            await self._open(server_id)

    async def remove(self, server_id: str) -> None:
        """Close the saved server `server_id` and forget it, its tools with it."""
        async with self._changing:
            self._refuse_unless_saved(server_id)
            await self._close(server_id)
            self._servers = {key: kept for key, kept in self._servers.items() if key != server_id}

    def _refuse_unless_saved(self, server_id: str) -> None:
        if server_id in self._built_in_ids:
            raise McpServerBuiltIn(f"{server_id} is built in; it cannot be changed here")
        if server_id not in self._servers:
            raise McpServerNotFound(f"no MCP server {server_id!r}")

    async def _close(self, server_id: str) -> None:
        running = self._connections.pop(server_id, None)
        if running is not None:
            await running.aclose()

    async def _open(self, server_id: str) -> None:
        """Start `server_id` with its config env and saved keys, or leave it waiting for a key."""
        saved = await asyncio.to_thread(self._keys.capability_keys, server_id)
        server = with_saved_keys(self._servers[server_id], saved)
        connection = Connection(id=server_id, server=server, factory=self._factory)
        self._connections[server_id] = connection
        missing = missing_keys(server)
        if missing:
            connection.wait_for(missing)
        else:
            connection.start()

    async def _required_refusal(self) -> str | None:
        """Wait for every required server to connect or fail, then say why startup must stop."""
        required = [c for c in self._connections.values() if c.server.required]
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(REQUIRED_CONNECT_TIMEOUT_SECONDS):
                for connection in required:
                    await connection.settled.wait()
        return required_refusal(
            [connection.snapshot() for connection in required], REQUIRED_CONNECT_TIMEOUT_SECONDS
        )

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
