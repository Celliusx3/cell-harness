"""The commands a connection queues for the task that owns its session."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mcp.types import CallToolResult, ReadResourceResult


@dataclass
class ToolCallCommand:
    server_tool_name: str
    arguments: dict[str, object]
    deadline: float
    reply: asyncio.Future[CallToolResult]

    def describe(self) -> str:
        return repr(self.server_tool_name)


@dataclass
class ResourceReadCommand:
    """`resources/read` — how an MCP App's HTML is fetched, over the same loop."""

    uri: str
    deadline: float
    reply: asyncio.Future[ReadResourceResult]

    def describe(self) -> str:
        return repr(self.uri)


Command = ToolCallCommand | ResourceReadCommand
