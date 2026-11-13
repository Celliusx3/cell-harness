"""The MCP session over stdio: one configured server, run as a child process."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import Client, StdioServerParameters
from mcp.client.extension import advertise
from mcp.client.stdio import stdio_client
from mcp.server.apps import APP_MIME_TYPE, EXTENSION_ID

from harness.mcp.client import McpClient
from harness.mcp.clients.stderr_tail import StderrTail, tee_stderr
from harness.mcp.domain.errors import McpConnectionError
from harness.mcp.domain.server import McpServer


@asynccontextmanager
async def open_stdio_client(server: McpServer) -> AsyncIterator[McpClient]:
    """A real stdio session for one configured server; one that dies first says why it did."""
    tail = tee_stderr(sys.stderr)
    connected = False
    try:
        async with _client(server, tail) as client:
            connected = True
            yield client
    except asyncio.CancelledError:
        raise
    except BaseException as err:  # anyio raises BaseExceptionGroup, which Exception misses
        last_words = "" if connected else tail.last_words()
        if not last_words:
            raise
        raise McpConnectionError(f"it exited before it connected: {last_words}") from err
    finally:
        tail.writer.close()


def _client(server: McpServer, tail: StderrTail) -> Client:
    parameters = StdioServerParameters(
        command=server.command, args=list(server.args), env=dict(server.env)
    )
    return Client(
        stdio_client(parameters, errlog=tail.writer),
        extensions=[advertise(EXTENSION_ID, {"mimeTypes": [APP_MIME_TYPE]})],
    )
