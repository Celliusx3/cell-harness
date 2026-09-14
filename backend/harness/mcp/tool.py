"""A server's tools, as tools the model can call.

The schema is relayed **verbatim** and `parse` is the identity — exactly what
`tools/definition.py` says to do when the schema comes from somewhere we do not
control. Validating against our own copy would silently drop arguments the
server accepts.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable, Iterable, Sequence

from mcp.types import CallToolResult, ContentBlock, ImageContent, TextContent, Tool

from harness.mcp.errors import McpNotConnectedError, McpTimeoutError
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
from harness.tools.progress import ToolProgressReporter

logger = logging.getLogger("harness.mcp")

# What every provider accepts for a tool name **and** what code mode can print.
# A violation is not this tool's problem alone: the request carries *every* tool,
# so one unusable name from one server fails the whole turn on every
# conversation. Such a tool is dropped.
#
# Deliberately narrower than the providers allow — they accept a hyphen, code
# mode does not. `tools/native/code/typescript.py` emits `declare function
# {name}(...)` unquoted, so a hyphenated tool name from a third-party server is
# unparseable TypeScript and would break the request for every other tool too.
# A hyphen is therefore *mapped* rather than dropped (see `namespaced`): it is
# what every public MCP App is named with, and the server never sees our spelling.
_VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

# Sent when a server publishes no schema. A bare `{}` or a null is rejected
# outright by some providers.
_EMPTY_SCHEMA = {"type": "object", "properties": {}}

CallTool = Callable[[str, dict], Awaitable[CallToolResult]]


def namespaced(server: str, tool: str) -> str:
    """`yt` + `get_subtitles` -> `yt__get_subtitles`. `_SERVER_ID` forbids an
    underscore in the id, so the split back is unambiguous, and forbids a hyphen
    so the result is a usable TypeScript identifier.

    A hyphen in the *tool* part becomes an underscore: `get-time` is what public
    MCP Apps are named, and the name only has to be ours on the model's side —
    `execute` still calls the server by the name it published.
    """
    return f"{server}{NAMESPACE}{tool.replace('-', '_')}"


def build_tools(server: str, tools: Iterable[Tool], call: CallTool) -> list[ToolDefinition[dict]]:
    """Every tool this server offers that the model can actually be told about."""
    built: list[ToolDefinition[dict]] = []
    seen: set[str] = set()
    for tool in tools:
        name = namespaced(server, tool.name)
        if not _VALID_NAME.match(name):
            logger.warning(
                "dropping MCP tool %r from %r: %r is not a usable tool name — it must be a "
                "valid identifier, because code mode declares it as a TypeScript function",
                tool.name,
                server,
                name,
            )
            continue
        if name in seen:
            # `get-video` and `get_video` on one server both spell `get_video`
            # here; the first published wins, because two tools under one name
            # would make the dispatcher's choice silent.
            logger.warning(
                "dropping MCP tool %r from %r: %r is already taken", tool.name, server, name
            )
            continue
        seen.add(name)
        built.append(mcp_tool(server=server, tool=tool, call=call))
    return built


def app_visible(tool: Tool) -> bool:
    """Whether an app may call this tool — `_meta.ui.visibility` includes `app`.

    Unset means both, per the extension: `["model", "app"]` is the default. A
    tool marked `["model"]` is the server saying the app must not call it.
    """
    ui = (tool.meta or {}).get("ui")
    visibility = ui.get("visibility") if isinstance(ui, dict) else None
    return "app" in visibility if isinstance(visibility, list) else True


def ui_resource_uri(tool: Tool) -> str | None:
    """The `ui://` resource an MCP App binds to this tool, if it declares one.

    `_meta.ui.resourceUri` per the MCP Apps extension. A tool may carry `ui`
    metadata without a resource — `visibility: ["app"]` alone marks a tool the
    app calls back — so the absence of the key is ordinary, not malformed.
    """
    ui = (tool.meta or {}).get("ui")
    uri = ui.get("resourceUri") if isinstance(ui, dict) else None
    return uri if isinstance(uri, str) and uri.startswith("ui://") else None


def mcp_tool(*, server: str, tool: Tool, call: CallTool) -> ToolDefinition[dict]:
    """One MCP tool, wired to the connection that owns it."""
    name = namespaced(server, tool.name)
    resource_uri = ui_resource_uri(tool)

    async def execute(arguments: dict, _progress: ToolProgressReporter) -> ToolOutcome:
        try:
            result = await call(tool.name, arguments)
        except McpNotConnectedError:
            # UNKNOWN_TOOL, not EXECUTION_ERROR: the model has to learn the tool
            # is *gone*, or it will keep retrying a server that is not there.
            return Failure(UNKNOWN_TOOL, f"{name} is no longer available: {server} is disconnected")
        except McpTimeoutError as err:
            return Failure(EXECUTION_ERROR, str(err))
        return outcome_of(result, name=name, server=server, resource_uri=resource_uri)

    return ToolDefinition(
        name=name,
        # No "(via {server})" suffix: the prefix already says where it came from,
        # and the description is the server's text, not ours to edit.
        description=tool.description or "",
        input_schema=tool.input_schema or dict(_EMPTY_SCHEMA),
        # Identity. The server owns validation — see the module docstring.
        parse=lambda raw: raw,
        execute=execute,
    )


def outcome_of(
    result: CallToolResult, *, name: str, server: str, resource_uri: str | None
) -> ToolOutcome:
    """What the model gets back.

    `is_error` is the trap: a tool that failed **returns** a result with the flag
    set rather than raising, so reading only `content` reports every failure as a
    success and the model never learns to recover.
    """
    rendered = render_content(result.content)
    if not rendered and result.structured_content is not None:
        rendered = json.dumps(result.structured_content)
    if result.is_error:
        return Failure(EXECUTION_ERROR, rendered or f"{name} reported an error with no message")
    # `structured_content` rides alongside rather than only standing in for empty
    # text. A server that sends both a summary and the rows means both, and
    # keeping only the summary threw the rows away with nothing able to ask for
    # them back.
    ui = (
        ToolUi(server=server, resource_uri=resource_uri, data=result.structured_content)
        if resource_uri is not None
        else None
    )
    return Ok(content=rendered, data=result.structured_content, ui=ui)


def render_content(blocks: Sequence[ContentBlock]) -> str:
    """Content blocks as the one string the model sees.

    Deliberately **not** truncated — the rendering layer handles overflow, and a
    result cap belongs in the tool pipeline where every tool gets it, not here.
    """
    parts: list[str] = []
    for block in blocks:
        match block:
            case TextContent():
                parts.append(block.text)
            case ImageContent():
                # A placeholder, never the payload: base64 here would enter the
                # session log and then every later model request, forever. A real
                # image belongs in tool-private presentation data.
                parts.append(f"[image {block.mime_type}, {len(block.data)} base64 chars]")
            case _:
                # Audio, embedded resources, and whatever a newer server invents.
                # Named rather than dropped, so the model can say what it got.
                parts.append(f"[{type(block).__name__}]")
    return "\n".join(parts)
