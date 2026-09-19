"""The yfinance seam with stub factories."""

from __future__ import annotations

import pandas as pd
import pytest

from markets.data import RateLimited, Unavailable
from markets.data.yfinance import YFinanceSource
from markets.symbol import parse
from tests.unit.test_mapping import bars, statement_frame


class FastInfo:
    """Raises from inside a lookup like the real one does for an unknown symbol."""

    def __init__(self, values: dict, broken: bool = False) -> None:
        self._values, self._broken = values, broken

    def __getitem__(self, key: str):
        if self._broken:
            raise KeyError("currentTradingPeriod")
        return self._values.get(key)


class StubTicker:
    def __init__(self, symbol: str, *, broken: bool = False, raise_with: Exception | None = None):
        self.symbol = symbol
        self.fast_info = FastInfo({"lastPrice": 10.46, "currency": "MYR"}, broken=broken)
        self.history_metadata = {"currency": "MYR"}
        self.info = {"longName": "Malayan Banking Berhad", "financialCurrency": "MYR"}
        self.news = [{"content": {"title": "t"}}]
        self.quarterly_income_stmt = statement_frame()
        self.income_stmt = pd.DataFrame()
        self.balance_sheet = statement_frame()
        self.quarterly_cashflow = statement_frame()
        self.calls: list[dict] = []
        self._raise = raise_with

    def history(self, **kwargs):
        if self._raise:
            raise self._raise
        self.calls.append(kwargs)
        return bars(3)


class StubSearch:
    def __init__(self, query: str) -> None:
        self.quotes = [{"symbol": "1155.KL", "quoteType": "EQUITY", "longname": query}]


def source(**kwargs) -> tuple[YFinanceSource, list[StubTicker]]:
    made: list[StubTicker] = []

    def factory(symbol: str) -> StubTicker:
        ticker = StubTicker(symbol, **kwargs)
        made.append(ticker)
        return ticker

    return YFinanceSource(max_rows=70, ticker_factory=factory, search_factory=StubSearch), made


async def test_search_goes_through_the_search_factory() -> None:
    src, _ = source()

    out = await src.search("maybank")

    assert [(c.id, c.name) for c in out] == [("1155.KL", "maybank")]


async def test_a_quote_reads_fast_info_key_by_key() -> None:
    src, made = source()

    out = await src.quote(parse("1155.KL"))

    assert (out.status, out.price, out.currency) == ("ok", 10.46, "MYR")
    assert made[0].symbol == "1155.KL"


async def test_a_broken_fast_info_is_not_found_rather_than_a_raise() -> None:
    src, _ = source(broken=True)

    out = await src.quote(parse("NOPE"))

    assert out.status == "not_found"


async def test_history_asks_for_adjusted_bars_and_reads_the_currency() -> None:
    src, made = source()

    out = await src.history(parse("1155.KL"), "1mo", "1wk")

    assert made[0].calls == [{"period": "1mo", "interval": "1wk", "auto_adjust": True}]
    assert out.currency == "MYR"
    assert len(out.rows) == 3


async def test_a_profile_reads_info() -> None:
    src, _ = source()

    assert (await src.profile(parse("1155.KL"))).name == "Malayan Banking Berhad"


@pytest.mark.parametrize(
    ("statement", "period", "status"),
    [("income", "quarterly", "ok"), ("income", "annual", "not_found"), ("balance", "annual", "ok")],
)
async def test_financials_pick_the_attribute_for_the_statement_and_period(
    statement: str, period: str, status: str
) -> None:
    src, _ = source()

    out = await src.financials(parse("1155.KL"), statement, period, 2)

    assert out.status == status
    assert out.currency == "MYR"


async def test_news_reads_the_news_attribute() -> None:
    src, _ = source()

    assert (await src.news(parse("1155.KL"), 5)).items[0].title == "t"


async def test_a_rate_limit_from_the_library_is_rate_limited() -> None:
    err = type("YFRateLimitError", (Exception,), {})("Too Many Requests")
    src, _ = source(raise_with=err)

    with pytest.raises(RateLimited, match="rate-limited"):
        await src.history(parse("AAPL"), "1mo", "1d")


async def test_any_other_raise_is_unavailable_and_names_the_source() -> None:
    src, _ = source(raise_with=ConnectionError("dns"))

    with pytest.raises(Unavailable, match="Yahoo Finance could not be read: ConnectionError"):
        await src.history(parse("AAPL"), "1mo", "1d")
