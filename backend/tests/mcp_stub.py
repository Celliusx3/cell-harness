"""A real stdio MCP server, for the one test that uses the real SDK.

Run as a subprocess: `[sys.executable, "-u", <this file>]`. Everything else
mocks at `ClientLike`, because the loop's contracts are about tasks and timeouts,
not about the wire.

`STUB_MODE=deaf` initializes normally and then never answers — which is how
"accepts connections but stops answering" is testable with no network and no
wedged server to find.
"""

from __future__ import annotations

import asyncio
import os

from mcp.server.apps import Apps, client_supports_apps
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context

APP = "ui://stub/app.html"
apps = Apps()


@apps.tool(resource_uri=APP, description="This server's pid, with a UI to show it in.")
async def show_pid(ctx: Context) -> dict[str, object]:
    """Rich only for a client that negotiated MCP Apps — proving ours did."""
    return {"pid": os.getpid(), "apps": client_supports_apps(ctx)}


apps.add_html_resource(APP, "<!doctype html><title>stub</title><p>stub app</p>")

server = MCPServer("stub", extensions=[apps])
DEAF = os.environ.get("STUB_MODE") == "deaf"


@server.tool()
async def echo(value: str) -> str:
    """Say it back."""
    if DEAF:
        await asyncio.sleep(3600)
    return f"echo: {value}"


@server.tool()
async def boom() -> str:
    """Always fails, so the client sees `is_error` rather than an exception."""
    raise RuntimeError("this tool always fails")


@server.tool()
async def whoami() -> int:
    """This server's pid, so a test can prove the process is gone."""
    return os.getpid()


if __name__ == "__main__":
    asyncio.run(server.run_stdio_async())
