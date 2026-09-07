"""The composition root, and nothing else.

Deliberately thin, matching the harness's own `web/server.py` — *"the
composition root alone"*. Everything it does is wire concrete things together
and start the transport; the tools live in `tools/`, acquisition in `media/`,
interpretation in `read/`. A dependency that is missing is a `TypeError` here
rather than a runtime surprise, which is the whole reason none of this needs an
injection framework.

**Nothing may be printed to stdout.** stdout is the MCP protocol. Logging goes to
stderr, which the harness attaches to its own — so diagnostics land in the
harness log rather than corrupting a JSON-RPC frame.
"""

from __future__ import annotations

import logging
import sys

from mcp.server import MCPServer

from instagram import tools
from instagram.command import run_command
from instagram.config import ConfigError, load
from instagram.media import source_for
from instagram.media.fetch import Fetcher
from instagram.media.store import sweep
from instagram.read import Reader
from instagram.read.http import ProviderHttp

logger = logging.getLogger("instagram")

# Swept once at startup rather than on a timer: a server that is not running
# accumulates nothing, so a background task would be a thing to own and cancel
# for a problem one sweep already solves.
CACHE_TTL_SECONDS = 24 * 60 * 60


def build(*, fetcher: Fetcher, reader: Reader) -> MCPServer:
    """An `MCPServer` with both tools bound to `fetcher` and `reader`."""
    return tools.register(
        MCPServer(name="instagram", version="0.1.0"), fetcher=fetcher, reader=reader
    )


def main() -> None:
    """Entry point. Refuses to start rather than starting broken."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    try:
        config = load()
    except ConfigError as err:
        # The harness logs this and the tools are simply absent from
        # `list_functions`, so the model discovers it has no Instagram capability
        # and reports that — rather than retrying a tool that cannot work.
        logger.error("instagram refusing to start: %s", err)
        raise SystemExit(2) from err

    removed = sweep(config.work_dir, older_than_seconds=CACHE_TTL_SECONDS)
    if removed:
        logger.info("swept %d cached reel(s)", removed)

    http = ProviderHttp(
        base_url=config.provider_base_url,
        api_key=config.provider_api_key,
        timeout_seconds=config.request_timeout_seconds,
    )
    server = build(
        fetcher=Fetcher(config=config, source=source_for(config), run=run_command),
        reader=Reader(config=config, http=http, run=run_command),
    )
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover - exercised by tests/integration
    main()
