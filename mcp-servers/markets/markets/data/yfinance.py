"""Listed equities and ETFs through yfinance — US, Bursa Malaysia, anything
Yahoo quotes.

yfinance is synchronous and does blocking network I/O, so every call goes
through `asyncio.to_thread` — off the event loop, or one slow symbol stalls
every sibling in a batch that is already racing the harness's 60s deadline.
The library is the only thing this module imports lazily; the translation to
our models is `mapping.py`, which never sees it.

What the library does on failure, verified live: an unknown symbol logs a 404
and returns an *empty* frame or a bare `info` dict rather than raising, so
"not found" is read from emptiness; a real rate limit raises
`YFRateLimitError`. Free data, no guarantees — the harness README calls Yahoo
best-effort for a reason.
"""

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
    """`ticker_factory` and `search_factory` default to the library's own
    classes; tests pass stubs that return fixture frames."""

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
            # Statements are reported in the filer's currency, which is not
            # always the trading currency — an ADR trades in USD and reports in
            # yen. `financialCurrency` is the one that labels these numbers.
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
        except Exception as err:  # noqa: BLE001 - the library raises many types for two meanings
            raise _translate(err) from err


def _fast_info(ticker: Any) -> dict[str, Any]:
    """`fast_info` is a lazy mapping that raises from *inside* a key lookup for
    an unknown symbol (a `KeyError` on an internal field, verified live), so
    each key is read on its own and a miss is a `None`, never a raise."""
    fast = ticker.fast_info
    out: dict[str, Any] = {}
    for key in _FAST_KEYS:
        try:
            out[key] = fast[key]
        except Exception:  # noqa: BLE001 - see above
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
