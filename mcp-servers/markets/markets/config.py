"""Settings from the environment, validated before the server binds.

Same shape and the same reason as the Places server's: a server that refuses to
start is absent from `list_functions`, so the model learns it has no markets
capability. One that starts and then 403s on every filing teaches the model to
retry a tool that cannot work.

Two things are required even though yfinance itself needs nothing:

- `SEC_USER_AGENT`. EDGAR's fair-access policy demands a declared
  `Name email` agent and answers a bare client with 403 (verified live). Not a
  secret — it belongs in the committed `env`.
- `COINGECKO_API_KEY`. The keyless public endpoint rate-limited a probe after
  five calls; the free Demo key is what makes crypto work at all.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

EDGAR_DATA_URL = "https://data.sec.gov"
EDGAR_WWW_URL = "https://www.sec.gov"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# A history result is re-sent to the model on every later turn, so rows are
# the price of the call: 70 bars pretty-print to ~12 KB, 130 to ~23 KB
# (measured). 70 fits three months of daily bars, a year of weekly ones or
# five years of monthly ones, and the description tells the model to choose
# the interval so the range fits.
DEFAULT_MAX_ROWS = 70


class ConfigError(RuntimeError):
    """Startup refused. The message names the variable to set."""


@dataclass(frozen=True)
class Config:
    sec_user_agent: str
    coingecko_api_key: str
    max_rows: int
    max_ids: int
    call_budget_seconds: float
    timeout_seconds: float
    edgar_data_url: str
    edgar_www_url: str
    coingecko_base_url: str


def load(env: Mapping[str, str] | None = None) -> Config:
    src = os.environ if env is None else env

    agent = src.get("SEC_USER_AGENT", "").strip()
    if not agent:
        raise ConfigError(
            "SEC_USER_AGENT is not set — EDGAR requires a declared 'Name email' User-Agent "
            "(https://www.sec.gov/os/accessing-edgar-data); no signup, any real contact works"
        )

    key = src.get("COINGECKO_API_KEY", "").strip()
    if not key:
        raise ConfigError(
            "COINGECKO_API_KEY is not set — a free Demo key from "
            "https://www.coingecko.com/en/api/pricing (no billing) is enough"
        )

    return Config(
        sec_user_agent=agent,
        coingecko_api_key=key,
        max_rows=_int(src, "MARKETS_MAX_ROWS", DEFAULT_MAX_ROWS, 10, 1000),
        max_ids=_int(src, "MARKETS_MAX_IDS", 10, 1, 50),
        call_budget_seconds=_float(src, "MARKETS_CALL_BUDGET_SECONDS", 45.0),
        timeout_seconds=_float(src, "MARKETS_TIMEOUT_SECONDS", 20.0),
        edgar_data_url=src.get("MARKETS_EDGAR_DATA_URL", "").strip() or EDGAR_DATA_URL,
        edgar_www_url=src.get("MARKETS_EDGAR_WWW_URL", "").strip() or EDGAR_WWW_URL,
        coingecko_base_url=src.get("MARKETS_COINGECKO_BASE_URL", "").strip() or COINGECKO_BASE_URL,
    )


def _int(src: Mapping[str, str], name: str, default: int, lo: int, hi: int) -> int:
    raw = src.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError as err:
        raise ConfigError(f"{name}={raw!r} is not an integer") from err
    if not lo <= value <= hi:
        raise ConfigError(f"{name}={value} must be between {lo} and {hi}")
    return value


def _float(src: Mapping[str, str], name: str, default: float) -> float:
    raw = src.get(name, "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError as err:
        raise ConfigError(f"{name}={raw!r} is not a number") from err
    if value <= 0:
        raise ConfigError(f"{name}={value} must be greater than zero")
    return value
