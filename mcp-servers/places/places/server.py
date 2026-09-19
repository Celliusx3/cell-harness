"""The composition root, and nothing else."""

from __future__ import annotations

import logging
import sys

from mcp.server import MCPServer

from places import tools
from places.config import Config, ConfigError, load
from places.lookup import PlacesClient

logger = logging.getLogger("places")


def build(*, config: Config, client: PlacesClient) -> MCPServer:
    return tools.register(MCPServer(name="places", version="0.1.0"), config=config, client=client)


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    try:
        config = load()
    except ConfigError as err:
        logger.error("places refusing to start: %s", err)
        raise SystemExit(2) from err

    build(
        config=config,
        client=PlacesClient(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
        ),
    ).run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
