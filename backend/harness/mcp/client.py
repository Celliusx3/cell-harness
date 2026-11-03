"""What this package needs of an MCP session."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from mcp.types import CallToolResult, ListToolsResult, ReadResourceResult

from harness.config.sections import McpServer


class McpClient(Protocol):
    """One live session to one configured server."""

    async def list_tools(self, *, cursor: str | None = None) -> ListToolsResult: ...

    async def call_tool(self, server_tool_name: str, arguments: dict) -> CallToolResult: ...

    async def read_resource(self, uri: str) -> ReadResourceResult: ...


McpClientFactory = Callable[[McpServer], AbstractAsyncContextManager[McpClient]]
