"""The composition root, and nothing else.

Deliberately thin, matching the harness's own `web/server.py`. The tools live
in `tools/`, the sources in `data/`, `coingecko/` and `edgar/`.

**Nothing may be printed to stdout.** stdout is the MCP protocol; logging goes
to stderr, which the harness attaches to its own. yfinance logs through the
standard `logging` module, so it lands there too.
"""

from __future__ import annotations

import logging
import sys

from mcp.server import MCPServer

from markets import tools
from markets.coingecko import CoinGeckoSource
from markets.config import Config, ConfigError, load
from markets.data import MarketData
from markets.data.yfinance import YFinanceSource
from markets.edgar import EdgarClient

logger = logging.getLogger("markets")


def build(
    *, config: Config, market: MarketData, crypto: MarketData, edgar: EdgarClient
) -> MCPServer:
    return tools.register(
        MCPServer(name="markets", version="0.1.0"),
        config=config,
        market=market,
        crypto=crypto,
        edgar=edgar,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    try:
        config = load()
    except ConfigError as err:
        logger.error("markets refusing to start: %s", err)
        raise SystemExit(2) from err

    market = YFinanceSource(max_rows=config.max_rows)
    build(
        config=config,
        market=market,
        crypto=CoinGeckoSource(
            api_key=config.coingecko_api_key,
            base_url=config.coingecko_base_url,
            timeout_seconds=config.timeout_seconds,
            max_rows=config.max_rows,
            headlines=market,
        ),
        edgar=EdgarClient(
            user_agent=config.sec_user_agent,
            data_url=config.edgar_data_url,
            www_url=config.edgar_www_url,
            timeout_seconds=config.timeout_seconds,
        ),
    ).run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover - exercised by tests/integration
    main()
