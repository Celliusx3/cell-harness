"""A server's tools, as tools the model can call."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Iterable

from mcp.types import CallToolResult
from mcp.types import Tool as McpTool

from harness.mcp.errors import McpNotConnectedError, McpTimeoutError
from harness.mcp.result import outcome_of
from harness.tools import (
    EXECUTION_ERROR,
    NAMESPACE_SEPARATOR,
    UNKNOWN_TOOL,
    Failure,
    Tool,
    ToolContext,
    ToolOutcome,
)

logger = logging.getLogger("harness.mcp")

_TS_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

_WORD_BREAK = re.compile(r"[_-]|(?<=[a-z0-9])(?=[A-Z])")

_READ_VERBS = frozenset({"get", "list", "search", "find", "read", "fetch"})

# Some providers reject a bare `{}` or null schema.
_EMPTY_SCHEMA = {"type": "object", "properties": {}}

CallTool = Callable[[str, dict], Awaitable[CallToolResult]]


def namespaced(server: str, tool: str) -> str:
    """`yt` + `get_subtitles` -> `yt__get_subtitles`."""
    return f"{server}{NAMESPACE_SEPARATOR}{tool.replace('-', '_')}"


def build_tools(server: str, tools: Iterable[McpTool], call: CallTool) -> list[Tool[dict]]:
    """Every tool this server offers that the model can actually be told about."""
    built: list[Tool[dict]] = []
    seen: set[str] = set()
    for tool in tools:
        name = namespaced(server, tool.name)
        if not _TS_IDENTIFIER.match(name):
            logger.warning(
                "dropping MCP tool %r from %r: %r is not a usable tool name — it must be a "
                "valid identifier, because code mode declares it as a TypeScript function",
                tool.name,
                server,
                name,
            )
            continue
        if name in seen:
            logger.warning(
                "dropping MCP tool %r from %r: %r is already taken", tool.name, server, name
            )
            continue
        seen.add(name)
        built.append(mcp_tool(server=server, tool=tool, call=call))
    return built


def app_visible(tool: McpTool) -> bool:
    """Whether an app may call this tool — `_meta.ui.visibility` includes `app`."""
    ui = (tool.meta or {}).get("ui")
    visibility = ui.get("visibility") if isinstance(ui, dict) else None
    return "app" in visibility if isinstance(visibility, list) else True


def can_write(tool: McpTool) -> bool:
    """Yes unless its name has a read verb."""
    words = {word.lower() for word in _WORD_BREAK.split(tool.name) if word}
    return _READ_VERBS.isdisjoint(words)


def ui_resource_uri(tool: McpTool) -> str | None:
    """The `ui://` resource an MCP App binds to this tool, if it declares one."""
    ui = (tool.meta or {}).get("ui")
    uri = ui.get("resourceUri") if isinstance(ui, dict) else None
    return uri if isinstance(uri, str) and uri.startswith("ui://") else None


def mcp_tool(*, server: str, tool: McpTool, call: CallTool) -> Tool[dict]:
    """One MCP tool, wired to the connection that owns it."""
    name = namespaced(server, tool.name)
    resource_uri = ui_resource_uri(tool)

    async def execute(arguments: dict, _context: ToolContext) -> ToolOutcome:
        try:
            result = await call(tool.name, arguments)
        except McpNotConnectedError:
            return Failure(UNKNOWN_TOOL, f"{name} is no longer available: {server} is disconnected")
        except McpTimeoutError as err:
            return Failure(EXECUTION_ERROR, str(err))
        return outcome_of(result, name=name, server=server, resource_uri=resource_uri)

    return Tool(
        name=name,
        description=tool.description or "",
        input_schema=tool.input_schema or dict(_EMPTY_SCHEMA),
        parse=lambda raw: raw,
        execute=execute,
    )
