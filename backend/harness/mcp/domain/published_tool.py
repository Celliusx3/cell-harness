"""What a server's published tool says about itself: its name to the model, who may call it."""

from __future__ import annotations

import re

from mcp.types import Tool as McpTool

from harness.tools import NAMESPACE_SEPARATOR

_WORD_BREAK = re.compile(r"[_-]|(?<=[a-z0-9])(?=[A-Z])")

_READ_VERBS = frozenset({"get", "list", "search", "find", "read", "fetch"})


def namespaced_tool_name(server_id: str, server_tool_name: str) -> str:
    """`yt` + `get_subtitles` -> `yt__get_subtitles`."""
    return f"{server_id}{NAMESPACE_SEPARATOR}{server_tool_name.replace('-', '_')}"


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
