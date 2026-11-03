"""The MCP session over stdio: one configured server, run as a child process."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager

from mcp import Client, StdioServerParameters
from mcp.client.extension import advertise
from mcp.server.apps import APP_MIME_TYPE, EXTENSION_ID

from harness.config.sections import McpServer
from harness.mcp.client import McpClient


def open_stdio_client(server: McpServer) -> AbstractAsyncContextManager[McpClient]:
    """A real stdio session for one configured server."""
    return Client(
        StdioServerParameters(
            command=server.command,
            args=list(server.args),
            # The MCP SDK merges a mapping onto its safe defaults; `{}` would strip `PATH`.
            env=dict(server.env) or None,
        ),
        extensions=[advertise(EXTENSION_ID, {"mimeTypes": [APP_MIME_TYPE]})],
    )
