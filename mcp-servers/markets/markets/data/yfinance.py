"""Listed equities and ETFs through yfinance — US, Bursa Malaysia, anything Yahoo quotes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from markets.data import RateLimited, Unavailable, mapping
from markets.models import (
    YAHOO,
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

_FAST_KEYS = (
    "lastPrice",
    "previousClose",
    "dayLow",
    "dayHigh",
    "yearLow",
    "yearHigh",
    "marketCap",
    "lastVolume",
    "currency",
    "exchange",
    "quoteType",
)

_STATEMENTS: dict[tuple[Statement, FiscalPeriod], str] = {
    ("income", "annual"): "income_stmt",
    ("income", "quarterly"): "quarterly_income_stmt",
    ("balance", "annual"): "balance_sheet",
    ("balance", "quarterly"): "quarterly_balance_sheet",
    ("cashflow", "annual"): "cashflow",
    ("cashflow", "quarterly"): "quarterly_cashflow",
}

SEARCH_RESULTS = 8


class YFinanceSource:
    """Quotes and history from yfinance, with injectable ticker and search factories."""

    def __init__(
        self,
        *,
        max_rows: int,
        ticker_factory: Callable[[str], Any] | None = None,
        search_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._max_rows = max_rows
        self._ticker = ticker_factory or _library_ticker
        self._search = search_factory or _library_search

    @property
    def name(self) -> str:
        return YAHOO

    async def search(self, query: str) -> list[Candidate]:
        quotes = await self._run(lambda: self._search(query).quotes)
        return mapping.candidates(quotes or [])

    async def quote(self, symbol: Symbol) -> Quote:
        fast = await self._run(lambda: _fast_info(self._ticker(symbol.key)))
        return mapping.quote(symbol.id, fast)

    async def history(self, symbol: Symbol, period: Range, interval: Interval) -> History:
        def blocking() -> tuple[Any, str]:
            ticker = self._ticker(symbol.key)
            frame = ticker.history(period=period, interval=interval, auto_adjust=True)
            meta = getattr(ticker, "history_metadata", None) or {}
            return frame, str(meta.get("currency") or "")

        frame, currency = await self._run(blocking)
        return mapping.history(
            symbol.id,
            frame,
            period=period,
            interval=interval,
            currency=currency,
            max_rows=self._max_rows,
        )

    async def profile(self, symbol: Symbol) -> Profile:
        info = await self._run(lambda: self._ticker(symbol.key).info or {})
        return mapping.profile(symbol.id, info)

    async def financials(
        self, symbol: Symbol, statement: Statement, period: FiscalPeriod, limit: int
    ) -> Financials:
        def blocking() -> tuple[Any, str]:
            ticker = self._ticker(symbol.key)
            frame = getattr(ticker, _STATEMENTS[(statement, period)])
            # Yahoo's `financialCurrency` labels the statements; `currency` is the trading one.
            info = ticker.info or {}
            return frame, str(info.get("financialCurrency") or info.get("currency") or "")

        frame, currency = await self._run(blocking)
        return mapping.financials(
            symbol.id, frame, statement=statement, period=period, currency=currency, limit=limit
        )

    async def news(self, symbol: Symbol, limit: int) -> News:
        items = await self._run(lambda: self._ticker(symbol.key).news or [])
        return mapping.news(symbol.id, items, limit)

    async def _run[T](self, blocking: Callable[[], T]) -> T:
        try:
            return await asyncio.to_thread(blocking)
        except Exception as err:
            raise _translate(err) from err


def _fast_info(ticker: Any) -> dict[str, Any]:
    """Each `_FAST_KEYS` value from `ticker.fast_info`, `None` where the lookup raises."""
    fast = ticker.fast_info
    out: dict[str, Any] = {}
    for key in _FAST_KEYS:
        try:
            out[key] = fast[key]
        except Exception:  # yfinance raises from inside the lookup for an unknown symbol
            out[key] = None
    return out


def _translate(err: Exception) -> Exception:
    text = str(err)
    lowered = text.lower()
    if type(err).__name__ == "YFRateLimitError" or "too many requests" in lowered:
        return RateLimited(f"Yahoo Finance rate-limited the request: {text or 'HTTP 429'}")
    return Unavailable(f"Yahoo Finance could not be read: {type(err).__name__}: {text}")


def _library_ticker(symbol: str) -> Any:
    import yfinance

    return yfinance.Ticker(symbol)


def _library_search(query: str) -> Any:
    import yfinance

    return yfinance.Search(query, max_results=SEARCH_RESULTS, news_count=0, lists_count=0)
