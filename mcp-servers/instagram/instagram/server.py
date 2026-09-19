"""The composition root, and nothing else."""

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


if __name__ == "__main__":  # pragma: no cover
    main()
