"""A server's tools, as tools the model can call."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable, Iterable, Sequence

from mcp.types import CallToolResult, ContentBlock, ImageContent, TextContent, Tool

from harness.mcp.errors import McpNotConnectedError, McpTimeoutError
from harness.tools.context import ToolContext
from harness.tools.definition import (
    EXECUTION_ERROR,
    NAMESPACE,
    UNKNOWN_TOOL,
    Failure,
    Ok,
    ToolDefinition,
    ToolOutcome,
    ToolUi,
)

logger = logging.getLogger("harness.mcp")

_TS_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

# Some providers reject a bare `{}` or null schema.
_EMPTY_SCHEMA = {"type": "object", "properties": {}}

CallTool = Callable[[str, dict], Awaitable[CallToolResult]]


def namespaced(server: str, tool: str) -> str:
    """`yt` + `get_subtitles` -> `yt__get_subtitles`."""
    return f"{server}{NAMESPACE}{tool.replace('-', '_')}"


def build_tools(server: str, tools: Iterable[Tool], call: CallTool) -> list[ToolDefinition[dict]]:
    """Every tool this server offers that the model can actually be told about."""
    built: list[ToolDefinition[dict]] = []
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


def app_visible(tool: Tool) -> bool:
    """Whether an app may call this tool — `_meta.ui.visibility` includes `app`."""
    ui = (tool.meta or {}).get("ui")
    visibility = ui.get("visibility") if isinstance(ui, dict) else None
    return "app" in visibility if isinstance(visibility, list) else True


def ui_resource_uri(tool: Tool) -> str | None:
    """The `ui://` resource an MCP App binds to this tool, if it declares one."""
    ui = (tool.meta or {}).get("ui")
    uri = ui.get("resourceUri") if isinstance(ui, dict) else None
    return uri if isinstance(uri, str) and uri.startswith("ui://") else None


def mcp_tool(*, server: str, tool: Tool, call: CallTool) -> ToolDefinition[dict]:
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

    return ToolDefinition(
        name=name,
        description=tool.description or "",
        input_schema=tool.input_schema or dict(_EMPTY_SCHEMA),
        parse=lambda raw: raw,
        execute=execute,
    )


def outcome_of(
    result: CallToolResult, *, name: str, server: str, resource_uri: str | None
) -> ToolOutcome:
    """What the model gets back."""
    rendered = render_content(result.content)
    if not rendered and result.structured_content is not None:
        rendered = json.dumps(result.structured_content)
    if result.is_error:
        return Failure(EXECUTION_ERROR, rendered or f"{name} reported an error with no message")
    ui = (
        ToolUi(server=server, resource_uri=resource_uri, data=result.structured_content)
        if resource_uri is not None
        else None
    )
    return Ok(content=rendered, data=result.structured_content, ui=ui)


def render_content(blocks: Sequence[ContentBlock]) -> str:
    """Content blocks as the one string the model sees."""
    parts: list[str] = []
    for block in blocks:
        match block:
            case TextContent():
                parts.append(block.text)
            case ImageContent():
                parts.append(f"[image {block.mime_type}, {len(block.data)} base64 chars]")
            case _:
                parts.append(f"[{type(block).__name__}]")
    return "\n".join(parts)
