"""Doubles for the MCP command loop."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from mcp.server.apps import APP_MIME_TYPE
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    ReadResourceResult,
    TextContent,
    TextResourceContents,
    Tool,
)

from harness.config.sections import McpServer


def tool(
    name: str, *, description: str = "", schema: dict | None = None, meta: dict | None = None
) -> Tool:
    return Tool(
        name=name,
        description=description,
        inputSchema=schema if schema is not None else {"type": "object", "properties": {}},
        meta=meta,
    )


def text_result(body: str, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=body)], isError=is_error)


def html_resource(
    uri: str, html: str, *, mime: str = APP_MIME_TYPE, meta: dict | None = None
) -> ReadResourceResult:
    """What `resources/read` answers for an MCP App's HTML."""
    return ReadResourceResult(
        contents=[TextResourceContents(uri=uri, mimeType=mime, text=html, meta=meta)]
    )


def servers(*ids: str, **overrides) -> dict[str, McpServer]:
    """A `settings.mcp.servers` mapping, for a store under test."""
    return {name: McpServer(command="does-not-run", **overrides) for name in (ids or ("stub",))}


@dataclass
class FakeClient:
    """A scripted session that records which task owns it."""

    tools: list[Tool] = field(default_factory=lambda: [tool("echo")])
    behaviour: dict[str, object] = field(default_factory=dict)
    entered_in: asyncio.Task | None = None
    exited_in: asyncio.Task | None = None
    calls: list[tuple[str, dict]] = field(default_factory=list)
    pages: int = 1
    resources: dict[str, ReadResourceResult | float] = field(default_factory=dict)
    reads: list[str] = field(default_factory=list)

    async def list_tools(self, *, cursor: str | None = None) -> ListToolsResult:
        index = int(cursor) if cursor else 0
        size = max(1, len(self.tools) // self.pages) if self.pages > 1 else len(self.tools)
        chunk = self.tools[index : index + size]
        nxt = index + size
        return ListToolsResult(tools=chunk, nextCursor=str(nxt) if nxt < len(self.tools) else None)

    async def call_tool(self, name: str, arguments: dict) -> CallToolResult:
        self.calls.append((name, arguments))
        outcome = self.behaviour.get(name, f"{name} ok")
        if isinstance(outcome, float):
            await asyncio.sleep(outcome)
            return text_result(f"{name} finally")
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, CallToolResult):
            return outcome
        return text_result(str(outcome))

    async def read_resource(self, uri: str) -> ReadResourceResult:
        self.reads.append(uri)
        found = self.resources.get(uri)
        if found is None:
            raise ValueError(f"unknown resource {uri}")
        if isinstance(found, float):
            await asyncio.sleep(found)
            raise AssertionError("a slow read should have timed out")
        return found


@dataclass
class FakeFactory:
    """Hands out `FakeClient`s and counts how often it was asked."""

    client: FakeClient = field(default_factory=FakeClient)
    opens: int = 0
    connect_delay: float = 0.0
    connect_error: BaseException | None = None

    def __call__(self, _server: McpServer):
        @asynccontextmanager
        async def session():
            self.opens += 1
            if self.connect_delay:
                await asyncio.sleep(self.connect_delay)
            if self.connect_error is not None:
                raise self.connect_error
            self.client.entered_in = asyncio.current_task()
            try:
                yield self.client
            finally:
                self.client.exited_in = asyncio.current_task()

        return session()
