"""The MCP surface: seven tools over two data sources and EDGAR."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from markets.config import Config
from markets.data import MarketData, Unavailable
from markets.edgar import EdgarClient
from markets.models import (
    Filings,
    Financials,
    FiscalPeriod,
    History,
    Interval,
    News,
    Profile,
    Quote,
    Quotes,
    Range,
    SearchResult,
    Statement,
    now_iso,
)
from markets.symbol import Symbol, SymbolError, parse
from markets.tools import descriptions as d
from markets.tools.budget import with_budget

QUOTE_CONCURRENCY = 4
MAX_PERIODS = 8
MAX_FILINGS = 40
MAX_NEWS = 20


def register(
    server: MCPServer,
    *,
    config: Config,
    market: MarketData,
    crypto: MarketData,
    edgar: EdgarClient,
) -> MCPServer:
    def pick(symbol: Symbol) -> MarketData:
        return crypto if symbol.is_crypto else market

    @server.tool(name="search_symbol", description=d.SEARCH)
    async def search_symbol(
        query: str, kind: Literal["stock", "etf", "crypto"] | None = None
    ) -> SearchResult:
        query = query.strip()
        if not query:
            raise ToolError("query is empty")
        sources = [market, crypto] if kind is None else [crypto if kind == "crypto" else market]
        settled = await asyncio.gather(*(s.search(query) for s in sources), return_exceptions=True)
        candidates, notes = [], []
        for source, result in zip(sources, settled, strict=True):
            if isinstance(result, BaseException):
                notes.append(f"{source.name} was unavailable: {result}")
            else:
                candidates.extend(c for c in result if kind in (None, c.kind))
        if len(notes) == len(sources):
            raise ToolError("; ".join(notes))
        if not candidates:
            notes.append(
                "no match; try the company's or coin's name rather than a guessed ticker, "
                "or a shorter query"
            )
        return SearchResult(
            query_sent=query,
            candidates=candidates,
            detail="; ".join(notes),
            as_of=now_iso(),
            source=", ".join(s.name for s in sources),
        )

    @server.tool(name="get_quote", description=d.QUOTE)
    async def get_quote(ids: list[str]) -> Quotes:
        if not ids:
            raise ToolError("ids is empty")
        if len(ids) > config.max_ids:
            raise ToolError(f"at most {config.max_ids} ids per call; split the list")

        async def one(raw: str) -> Quote:
            try:
                symbol = parse(raw)
                return await pick(symbol).quote(symbol)
            except SymbolError as err:
                return _quote_problem(raw, "error", str(err))
            except Unavailable as err:
                return _quote_problem(raw, "error", str(err))

        items = await with_budget(
            ids,
            one,
            seconds=config.call_budget_seconds,
            concurrency=QUOTE_CONCURRENCY,
            on_timeout=lambda raw: _quote_problem(
                raw, "timeout", "did not finish within the call budget; ask again for this id"
            ),
        )
        return Quotes(items=items, as_of=now_iso())

    @server.tool(name="get_price_history", description=d.HISTORY)
    async def get_price_history(
        id: str, period: Range = "3mo", interval: Interval = "1d"
    ) -> History:
        symbol = _parse(id)
        return await _guard(pick(symbol).history(symbol, period, interval))

    @server.tool(name="get_company_profile", description=d.PROFILE)
    async def get_company_profile(id: str) -> Profile:
        symbol = _parse(id)
        return await _guard(pick(symbol).profile(symbol))

    @server.tool(name="get_financials", description=d.FINANCIALS)
    async def get_financials(
        id: str, statement: Statement, period: FiscalPeriod = "annual", limit: int = 4
    ) -> Financials:
        symbol = _parse(id)
        return await _guard(
            pick(symbol).financials(symbol, statement, period, _clamp(limit, MAX_PERIODS))
        )

    @server.tool(name="get_filings", description=d.FILINGS)
    async def get_filings(id: str, form: str | None = None, limit: int = 10) -> Filings:
        symbol = _parse(id)
        return await _guard(edgar.filings(symbol, form, _clamp(limit, MAX_FILINGS)))

    @server.tool(name="get_news", description=d.NEWS)
    async def get_news(id: str, limit: int = 8) -> News:
        symbol = _parse(id)
        return await _guard(pick(symbol).news(symbol, _clamp(limit, MAX_NEWS)))

    return server


def _parse(raw: str) -> Symbol:
    try:
        return parse(raw)
    except SymbolError as err:
        raise ToolError(str(err)) from err


async def _guard[T](work: Awaitable[T]) -> T:
    try:
        return await work
    except Unavailable as err:
        raise ToolError(str(err)) from err


def _clamp(limit: int, cap: int) -> int:
    return max(1, min(limit, cap))


def _quote_problem(raw: str, status: Literal["error", "timeout"], detail: str) -> Quote:
    return Quote(id=raw.strip(), status=status, detail=detail, as_of=now_iso(), source="")
