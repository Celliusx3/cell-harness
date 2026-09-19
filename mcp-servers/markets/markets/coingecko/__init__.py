"""Coins through CoinGecko's Demo API."""

from __future__ import annotations

from typing import Any

import httpx

from markets.coingecko import mapping
from markets.data import MarketData, RateLimited, Unavailable
from markets.models import (
    COINGECKO,
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
    now_iso,
)
from markets.symbol import Symbol

_DAYS: dict[Range, int] = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5y": 365}
_CAPPED = "CoinGecko's free plan holds one year of history, so 5y is served as 1y"


class CoinGeckoSource:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_rows: int,
        headlines: MarketData,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._max_rows = max_rows
        self._headlines = headlines
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._headers = {"x-cg-demo-api-key": api_key, "Accept": "application/json"}

    @property
    def name(self) -> str:
        return COINGECKO

    async def search(self, query: str) -> list[Candidate]:
        payload = await self._get("/search", {"query": query})
        return mapping.candidates((payload or {}).get("coins") or [])

    async def quote(self, symbol: Symbol) -> Quote:
        rows = await self._get("/coins/markets", {"vs_currency": mapping.VS, "ids": symbol.key})
        return mapping.quote(symbol.id, rows[0] if rows else None)

    async def history(self, symbol: Symbol, period: Range, interval: Interval) -> History:
        chart = await self._get(
            f"/coins/{symbol.key}/market_chart",
            {"vs_currency": mapping.VS, "days": _DAYS[period]},
            not_found_ok=True,
        )
        if chart is None:
            return History(
                id=symbol.id,
                status="not_found",
                detail="CoinGecko knows no coin with this id; find it with search_symbol",
                period=period,
                interval=interval,
                as_of=now_iso(),
                source=COINGECKO,
            )
        return mapping.history(
            symbol.id,
            chart,
            period=period,
            interval=interval,
            max_rows=self._max_rows,
            detail=_CAPPED if period == "5y" else "",
        )

    async def profile(self, symbol: Symbol) -> Profile:
        coin = await self._get(
            f"/coins/{symbol.key}",
            {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
            not_found_ok=True,
        )
        if coin is None:
            return Profile(
                id=symbol.id,
                status="not_found",
                detail="CoinGecko knows no coin with this id; find it with search_symbol",
                as_of=now_iso(),
                source=COINGECKO,
            )
        return mapping.profile(symbol.id, coin)

    async def news(self, symbol: Symbol, limit: int) -> News:
        rows = await self._get("/coins/markets", {"vs_currency": mapping.VS, "ids": symbol.key})
        ticker = str(rows[0].get("symbol") or "").upper() if rows else ""
        if not ticker:
            return News(
                id=symbol.id,
                status="not_found",
                detail="CoinGecko knows no coin with this id; find it with search_symbol",
                as_of=now_iso(),
                source=COINGECKO,
            )
        yahoo = Symbol(id=symbol.id, key=f"{ticker}-{mapping.VS.upper()}", is_crypto=False)
        return replace_id(await self._headlines.news(yahoo, limit), symbol.id)

    async def financials(
        self, symbol: Symbol, statement: Statement, period: FiscalPeriod, limit: int
    ) -> Financials:
        return Financials(
            id=symbol.id,
            status="unsupported",
            detail="A coin files no financial statements; get_company_profile carries supply, "
            "market cap and all-time high instead",
            statement=statement,
            period=period,
            as_of=now_iso(),
            source=COINGECKO,
        )

    async def _get(self, path: str, params: dict[str, Any], *, not_found_ok: bool = False) -> Any:
        try:
            response = await self._client.get(
                f"{self._base}{path}", params=params, headers=self._headers
            )
        except httpx.HTTPError as err:
            raise Unavailable(f"CoinGecko could not be reached: {err}") from err
        if response.status_code == 429:
            raise RateLimited("CoinGecko rate-limited the request (Demo: ~30/min); wait a minute")
        if response.status_code in (401, 403):
            raise Unavailable("CoinGecko rejected the API key (COINGECKO_API_KEY)")
        if response.status_code == 404 and not_found_ok:
            return None
        if response.status_code != 200:
            raise Unavailable(f"CoinGecko answered HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as err:
            raise Unavailable("CoinGecko answered with something that is not JSON") from err


def replace_id(news: News, id: str) -> News:
    """`news` with its id replaced by `id`."""
    return news.model_copy(update={"id": id})
