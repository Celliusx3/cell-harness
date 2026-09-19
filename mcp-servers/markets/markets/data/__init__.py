"""The seam between the tools and where market data comes from."""

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
