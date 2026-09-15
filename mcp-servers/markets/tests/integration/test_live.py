"""The real sources, once, to re-verify the shapes the fixtures were written
from. Opt-in — `MARKETS_LIVE=1` — because it needs the network and a
CoinGecko key, and free sources are allowed to be flaky."""

from __future__ import annotations

import os

import pytest

from markets.coingecko import CoinGeckoSource
from markets.config import load
from markets.data.yfinance import YFinanceSource
from markets.edgar import EdgarClient
from markets.symbol import parse

pytestmark = pytest.mark.skipif(os.environ.get("MARKETS_LIVE") != "1", reason="MARKETS_LIVE=1")


async def test_a_bursa_stock_quotes_in_ringgit_and_has_statements() -> None:
    yahoo = YFinanceSource(max_rows=70)

    quote = await yahoo.quote(parse("1155.KL"))
    profile = await yahoo.profile(parse("1155.KL"))
    income = await yahoo.financials(parse("1155.KL"), "income", "quarterly", 2)

    assert (quote.status, quote.currency) == ("ok", "MYR")
    assert profile.name == "Malayan Banking Berhad"
    assert income.status == "ok" and income.currency == "MYR"
    assert "Net Income" in income.periods[0].items


async def test_search_ranks_the_named_company_first() -> None:
    out = await YFinanceSource(max_rows=70).search("public bank")

    assert out[0].id == "1295.KL"


async def test_edgar_lists_apple_ten_qs_with_urls() -> None:
    config = load()
    edgar = EdgarClient(
        user_agent=config.sec_user_agent,
        data_url=config.edgar_data_url,
        www_url=config.edgar_www_url,
        timeout_seconds=config.timeout_seconds,
    )

    out = await edgar.filings(parse("AAPL"), "10-Q", 1)

    assert out.status == "ok" and out.filings[0].url.startswith("https://www.sec.gov/Archives/")


async def test_coingecko_finds_bitcoin_and_charts_it() -> None:
    config = load()
    yahoo = YFinanceSource(max_rows=70)
    gecko = CoinGeckoSource(
        api_key=config.coingecko_api_key,
        base_url=config.coingecko_base_url,
        timeout_seconds=config.timeout_seconds,
        max_rows=70,
        headlines=yahoo,
    )

    search = await gecko.search("bitcoin")
    history = await gecko.history(parse("crypto:bitcoin"), "6mo", "1wk")
    news = await gecko.news(parse("crypto:bitcoin"), 2)

    assert search[0].id == "crypto:bitcoin"
    assert history.status == "ok" and 20 <= len(history.rows) <= 28
    assert news.status == "ok" and news.id == "crypto:bitcoin"
