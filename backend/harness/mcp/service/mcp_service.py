"""The saved MCP servers, started once their keys are found, and their tools."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

from mcp.server.apps import APP_MIME_TYPE
from mcp.types import CallToolResult, ReadResourceResult, TextResourceContents
from mcp.types import Tool as McpTool

from harness.mcp.domain.app_policy import AppPage, app_content_security_policy
from harness.mcp.domain.errors import (
    AppToolNotFound,
    AppToolRefused,
    McpNotConnectedError,
    McpServerNotFound,
    McpServerTaken,
    NotAnAppPage,
)
from harness.mcp.domain.mcp_server import McpServer, missing_keys
from harness.mcp.domain.published_tool import (
    UI_SCHEME,
    can_write,
    is_app_visible,
    namespaced_tool_name,
    ui_resource_uri,
)
from harness.mcp.domain.server_status import ServerStatus
from harness.mcp.service.connection import Connection
from harness.mcp.service.mcp_client import McpClientFactory
from harness.tools import Tool


class McpService:
    """The live connections to the saved servers, those waiting, and their tools."""

    def __init__(
        self,
        servers: Mapping[str, McpServer],
        *,
        client_factory: McpClientFactory,
    ) -> None:
        self._servers: Mapping[str, McpServer] = dict(servers)
        self._factory = client_factory
        self._connections: dict[str, Connection] = {}
        self._change_lock = asyncio.Lock()

    def tools(self) -> list[Tool[dict[str, object]]]:
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
            for tool in connection.published_tools
            if can_write(tool)
            and (tool_name := namespaced_tool_name(connection.id, tool.name)) in offered
        )

    def offered_from_start(self) -> frozenset[str]:
        """Every tool on offer now that its server's `offered` names, as the model calls it."""
        on_offer = {tool.name for tool in self.tools()}
        return frozenset(
            tool_name
            for server_id, server in self._servers.items()
            for name in server.offered
            if (tool_name := namespaced_tool_name(server_id, name)) in on_offer
        )

    def server(self, server_id: str) -> McpServer:
        """How `server_id` is run, its keys in its env. `KeyError` if not configured."""
        return self._servers[server_id]

    def published_tools(self, server_id: str) -> tuple[McpTool, ...]:
        """One server's tools as it published them. `KeyError` if not configured."""
        return self._connection(server_id).published_tools

    async def call_tool(
        self, server_id: str, server_tool_name: str, arguments: dict[str, object]
    ) -> CallToolResult:
        """One `tools/call` on one server, answered verbatim, proxied for an MCP App."""
        return await self._connection(server_id).call_tool(server_tool_name, arguments, None)

    async def read_resource(self, server_id: str, uri: str) -> ReadResourceResult:
        """One `resources/read` on one server — the browser fetching an app's HTML."""
        return await self._connection(server_id).read_resource(uri)

    async def app_page(self, server_id: str, uri: str) -> AppPage:
        """The app page `uri` names on `server_id`; `NotAnAppPage` for any other resource."""
        self._refuse_unless_served(server_id)
        if not uri.startswith(UI_SCHEME):
            raise NotAnAppPage(f"{uri!r} is not a ui:// resource")
        result = await self.read_resource(server_id, uri)
        content = result.contents[0] if result.contents else None
        if not isinstance(content, TextResourceContents) or content.mime_type != APP_MIME_TYPE:
            raise NotAnAppPage(f"{uri!r} is not {APP_MIME_TYPE!r} text")
        return AppPage(
            html=content.text, content_security_policy=app_content_security_policy(content.meta)
        )

    async def call_app_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, object], app_uri: str
    ) -> CallToolResult:
        """`tool_name` called for the app at `app_uri`, when that app may call it; else refused."""
        self._refuse_unless_served(server_id)
        tool = next((t for t in self.published_tools(server_id) if t.name == tool_name), None)
        if tool is None:
            raise AppToolNotFound(f"{server_id} has no tool {tool_name!r}")
        if not is_app_visible(tool):
            raise AppToolRefused(f"{tool_name!r} is not callable by apps")
        bound = ui_resource_uri(tool)
        if bound is not None and bound != app_uri:
            raise AppToolRefused(f"{tool_name!r} belongs to another app, {bound}")
        return await self.call_tool(server_id, tool_name, arguments)

    def _connection(self, server_id: str) -> Connection:
        """The connection for a configured server; `KeyError` for one that is not."""
        if server_id not in self._servers:
            raise KeyError(server_id)
        if server_id not in self._connections:
            raise McpNotConnectedError(f"{server_id} is not connected")
        return self._connections[server_id]

    async def start(self) -> None:
        """Start every server whose keys are found, waiting for none of them to connect."""
        async with self._change_lock:
            for server_id in self._servers:
                await self._open(server_id)

    async def restart(self, server_id: str) -> None:
        """Close `server_id`, then open it again. `KeyError` if unknown."""
        if server_id not in self._servers:
            raise KeyError(server_id)
        async with self._change_lock:
            running = self._connections.get(server_id)
            if running is not None:
                await running.aclose()
            await self._open(server_id)

    async def add(self, server_id: str, server: McpServer) -> None:
        """Serve `server` as `server_id` and start it; `McpServerTaken` if the id is served."""
        async with self._change_lock:
            if server_id in self._servers:
                raise McpServerTaken(f"a server is already named {server_id!r}")
            self._servers = {**self._servers, server_id: server}
            await self._open(server_id)

    async def change(self, server_id: str, server: McpServer) -> None:
        """Close the server `server_id`, then start it again as `server`."""
        async with self._change_lock:
            self._refuse_unless_served(server_id)
            await self._close(server_id)
            self._servers = {**self._servers, server_id: server}
            await self._open(server_id)

    async def remove(self, server_id: str) -> None:
        """Close the server `server_id` and forget it, its tools with it."""
        async with self._change_lock:
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
            connection.mark_waiting_for(missing)
        else:
            connection.start()

    async def aclose(self) -> None:
        async with self._change_lock:
            await asyncio.gather(
                *(connection.aclose() for connection in self._connections.values()),
                return_exceptions=True,
            )
            self._connections.clear()

    def statuses(self) -> list[ServerStatus]:
        """Every configured server: whether it came up, or the keys it waits for."""
        return [
            self._connections[server_id].server_status()
            if server_id in self._connections
            else ServerStatus(id=server_id, status="disconnected", error="", tool_names=())
            for server_id in self._servers
        ]
