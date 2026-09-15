"""The seam between the tools and where market data comes from.

Two rules copied from ai-hedge-fund's `DataClient` protocol, because they are
the difference between a result the model can trust and one it cannot:

- **Empty means "no data".** An unknown ticker or a coin with no statements is
  a `not_found` status on a normal result.
- **Infrastructure failure raises.** A dead network or a rate limit is
  `Unavailable` / `RateLimited`, and the tool layer decides whether that sinks
  the whole call (one id asked) or one item (a batch).

Both live sources — yfinance for listed equities, CoinGecko for coins — satisfy
the same Protocol, so the tools route on the id and nothing else. A question a
source cannot answer (statements for a coin) is an `unsupported` status with a
detail, so the routing needs no special cases.
"""

from __future__ import annotations

from typing import Protocol

from markets.models import (
    Candidate,
    Financials,
    FiscalPeriod,
    History,
    Interval,
    News,
    Profile,
    Quote,
    Range,
    Statement,
)
from markets.symbol import Symbol


class Unavailable(RuntimeError):
    """The source could not be reached or answered with nonsense."""


class RateLimited(Unavailable):
    """The source said to slow down. Waiting is the only fix."""


class MarketData(Protocol):
    @property
    def name(self) -> str: ...

    async def search(self, query: str) -> list[Candidate]: ...

    async def quote(self, symbol: Symbol) -> Quote: ...

    async def history(self, symbol: Symbol, period: Range, interval: Interval) -> History: ...

    async def profile(self, symbol: Symbol) -> Profile: ...

    async def news(self, symbol: Symbol, limit: int) -> News: ...

    async def financials(
        self, symbol: Symbol, statement: Statement, period: FiscalPeriod, limit: int
    ) -> Financials: ...
