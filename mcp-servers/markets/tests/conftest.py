"""Builders."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
import pytest

from markets.config import Config
from markets.data import MarketData
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

AS_OF = "2026-09-14T12:00:00+00:00"


def make_config(**overrides: object) -> Config:
    values: dict[str, object] = {
        "sec_user_agent": "tests tests@example.com",
        "coingecko_api_key": "CG-test",
        "max_rows": 70,
        "max_ids": 10,
        "call_budget_seconds": 5.0,
        "timeout_seconds": 5.0,
        "edgar_data_url": "https://data.sec.test",
        "edgar_www_url": "https://www.sec.test",
        "coingecko_base_url": "https://gecko.test/api/v3",
    }
    values.update(overrides)
    return Config(**values)


def ok_quote(id: str, price: float = 10.0, source: str = "fake") -> Quote:
    return Quote(id=id, status="ok", price=price, currency="USD", as_of=AS_OF, source=source)


class FakeMarket:
    """Canned answers per id."""

    def __init__(self, name: str = "fake") -> None:
        self._name = name
        self.candidates: list[Candidate] | Exception = []
        self.quotes: dict[str, Quote | Exception] = {}
        self.delay: dict[str, float] = {}
        self.calls: list[tuple[str, str, tuple[object, ...]]] = []

    @property
    def name(self) -> str:
        return self._name

    async def search(self, query: str) -> list[Candidate]:
        self.calls.append(("search", query, ()))
        if isinstance(self.candidates, Exception):
            raise self.candidates
        return list(self.candidates)

    async def quote(self, symbol: Symbol) -> Quote:
        self.calls.append(("quote", symbol.id, ()))
        await asyncio.sleep(self.delay.get(symbol.id, 0))
        found = self.quotes.get(symbol.id)
        if isinstance(found, Exception):
            raise found
        if found is None:
            return Quote(
                id=symbol.id, status="not_found", detail="nope", as_of=AS_OF, source=self._name
            )
        return found

    async def history(self, symbol: Symbol, period: Range, interval: Interval) -> History:
        self.calls.append(("history", symbol.id, (period, interval)))
        return History(
            id=symbol.id,
            status="ok",
            period=period,
            interval=interval,
            currency="USD",
            as_of=AS_OF,
            source=self._name,
        )

    async def profile(self, symbol: Symbol) -> Profile:
        self.calls.append(("profile", symbol.id, ()))
        return Profile(id=symbol.id, status="ok", name="Fake Co", as_of=AS_OF, source=self._name)

    async def financials(
        self, symbol: Symbol, statement: Statement, period: FiscalPeriod, limit: int
    ) -> Financials:
        self.calls.append(("financials", symbol.id, (statement, period, limit)))
        return Financials(
            id=symbol.id,
            status="ok",
            statement=statement,
            period=period,
            as_of=AS_OF,
            source=self._name,
        )

    async def news(self, symbol: Symbol, limit: int) -> News:
        self.calls.append(("news", symbol.id, (limit,)))
        return News(id=symbol.id, status="ok", as_of=AS_OF, source=self._name)


def capturing(
    respond: httpx.Response | Callable[[httpx.Request], httpx.Response],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    """A canned handler and the list of requests it saw."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return respond(request) if callable(respond) else respond

    return handler, seen


def http_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def server_with(
    *,
    market: MarketData | None = None,
    crypto: MarketData | None = None,
    edgar_handler=None,
    **config_overrides: object,
):
    """All halves wired into a real `MCPServer`."""
    from markets.edgar import EdgarClient
    from markets.server import build

    config = make_config(**config_overrides)
    return build(
        config=config,
        market=market or FakeMarket("yahoo"),
        crypto=crypto or FakeMarket("gecko"),
        edgar=EdgarClient(
            user_agent=config.sec_user_agent,
            data_url=config.edgar_data_url,
            www_url=config.edgar_www_url,
            timeout_seconds=config.timeout_seconds,
            client=http_client(edgar_handler or (lambda r: httpx.Response(500))),
        ),
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
