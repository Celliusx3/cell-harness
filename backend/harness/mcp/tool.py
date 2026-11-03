"""A server's tools, as tools the model can call."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Iterable

from mcp.types import CallToolResult
from mcp.types import Tool as McpTool

from harness.mcp._result import outcome_of
from harness.mcp.models.errors import McpNotConnectedError, McpTimeoutError
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


def namespaced(server_id: str, server_tool_name: str) -> str:
    """`yt` + `get_subtitles` -> `yt__get_subtitles`."""
    return f"{server_id}{NAMESPACE_SEPARATOR}{server_tool_name.replace('-', '_')}"


def build_tools(server_id: str, published: Iterable[McpTool], call: CallTool) -> list[Tool[dict]]:
    """Every tool this server offers that the model can actually be told about."""
    built: list[Tool[dict]] = []
    seen: set[str] = set()
    for tool in published:
        tool_name = namespaced(server_id, tool.name)
        if not _TS_IDENTIFIER.match(tool_name):
            logger.warning(
                "dropping MCP tool %r from %r: %r is not a usable tool name — it must be a "
                "valid identifier, because code mode declares it as a TypeScript function",
                tool.name,
                server_id,
                tool_name,
            )
            continue
        if tool_name in seen:
            logger.warning(
                "dropping MCP tool %r from %r: %r is already taken", tool.name, server_id, tool_name
            )
            continue
        seen.add(tool_name)
        built.append(as_tool(server_id=server_id, published=tool, call=call))
    return built


def is_app_visible(tool: McpTool) -> bool:
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


def as_tool(*, server_id: str, published: McpTool, call: CallTool) -> Tool[dict]:
    """One MCP tool, wired to the connection that owns it."""
    tool_name = namespaced(server_id, published.name)
    resource_uri = ui_resource_uri(published)

    async def execute(arguments: dict, _context: ToolContext) -> ToolOutcome:
        try:
            result = await call(published.name, arguments)
        except McpNotConnectedError:
            return Failure(
                UNKNOWN_TOOL, f"{tool_name} is no longer available: {server_id} is disconnected"
            )
        except McpTimeoutError as err:
            return Failure(EXECUTION_ERROR, str(err))
        return outcome_of(
            result, tool_name=tool_name, server_id=server_id, resource_uri=resource_uri
        )

    return Tool(
        name=tool_name,
        description=published.description or "",
        input_schema=published.input_schema or dict(_EMPTY_SCHEMA),
        parse=lambda raw: raw,
        execute=execute,
    )
