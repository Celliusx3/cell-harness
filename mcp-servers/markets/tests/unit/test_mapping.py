"""yfinance's shapes into ours, with frames built by hand from the shapes
recorded on 2026-09-14. No network."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from markets.data import mapping
from markets.models import YAHOO


def bars(n: int, start: float = 100.0) -> pd.DataFrame:
    index = pd.date_range("2026-01-05", periods=n, freq="B", tz="Asia/Kuala_Lumpur")
    closes = [start + i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 0.5 for c in closes],
            "High": [c + 1.0 for c in closes],
            "Low": [c - 1.0 for c in closes],
            "Close": closes,
            "Volume": [1000 + i for i in range(n)],
            "Dividends": [0.0] * n,
            "Stock Splits": [0.0] * n,
        },
        index=index,
    )


# --- search --------------------------------------------------------------


def test_search_keeps_equities_and_etfs_and_drops_the_rest() -> None:
    quotes = [
        {"symbol": "AAPL", "quoteType": "EQUITY", "exchDisp": "NASDAQ", "longname": "Apple Inc."},
        {"symbol": "SAAPL=F", "quoteType": "FUTURE", "shortname": "Apple futures"},
        {"symbol": "SPY", "quoteType": "ETF", "exchDisp": "NYSEArca", "shortname": "SPDR S&P"},
        {"symbol": "0P0001.SI", "quoteType": "MUTUALFUND"},
        {"quoteType": "EQUITY"},
    ]

    out = mapping.candidates(quotes)

    assert [(c.id, c.name, c.exchange, c.kind) for c in out] == [
        ("AAPL", "Apple Inc.", "NASDAQ", "stock"),
        ("SPY", "SPDR S&P", "NYSEArca", "etf"),
    ]


# --- quote ---------------------------------------------------------------


def test_a_quote_reads_fast_info_and_computes_the_change() -> None:
    fast = {
        "lastPrice": 10.460000038146973,
        "previousClose": 10.38,
        "dayLow": 10.38,
        "dayHigh": 10.48,
        "yearLow": 9.79,
        "yearHigh": 12.42,
        "marketCap": 126519759071.2,
        "lastVolume": 6491800,
        "currency": "MYR",
        "exchange": "KLS",
        "quoteType": "EQUITY",
    }

    quote = mapping.quote("1155.KL", fast)

    assert quote.status == "ok"
    assert quote.price == 10.46  # float32 noise rounded away
    assert quote.change_pct == pytest.approx(0.7707, abs=1e-4)
    assert (quote.currency, quote.exchange, quote.kind) == ("MYR", "KLS", "stock")
    assert quote.source == YAHOO


def test_a_quote_with_no_price_is_not_found_not_an_error() -> None:
    quote = mapping.quote("NOPE", {"lastPrice": None, "currency": None})

    assert quote.status == "not_found"
    assert "search_symbol" in quote.detail


def test_a_quote_without_a_previous_close_has_no_change() -> None:
    quote = mapping.quote("X", {"lastPrice": 5.0, "previousClose": None})

    assert quote.change_pct is None


# --- history -------------------------------------------------------------


def test_history_rows_are_dated_ohlcv_in_order() -> None:
    out = mapping.history("X", bars(3), period="1mo", interval="1d", currency="MYR", max_rows=70)

    assert out.status == "ok"
    assert [r.date for r in out.rows] == ["2026-01-05", "2026-01-06", "2026-01-07"]
    assert out.rows[0].model_dump() == {
        "date": "2026-01-05",
        "open": 99.5,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1000.0,
    }
    assert out.currency == "MYR"
    assert out.adjusted is True
    assert not out.truncated


def test_history_keeps_the_latest_rows_and_names_the_coarser_interval() -> None:
    out = mapping.history("X", bars(10), period="1y", interval="1d", currency="", max_rows=4)

    assert out.truncated
    assert len(out.rows) == 4
    assert out.rows[-1].close == 109.0
    assert "latest 4 of 10" in out.detail
    assert "interval 1wk" in out.detail


def test_history_at_the_coarsest_interval_has_no_coarser_hint() -> None:
    out = mapping.history("X", bars(10), period="5y", interval="1mo", currency="", max_rows=4)

    assert "interval" not in out.detail


def test_the_summary_spans_the_whole_range_even_when_rows_are_cut() -> None:
    out = mapping.history("X", bars(10), period="1y", interval="1d", currency="", max_rows=2)

    assert out.summary is not None
    assert (out.summary.first_close, out.summary.last_close) == (100.0, 109.0)
    assert (out.summary.high, out.summary.low) == (110.0, 99.0)
    assert out.summary.change_pct == 9.0


def test_an_empty_frame_is_not_found() -> None:
    out = mapping.history("X", pd.DataFrame(), period="1mo", interval="1d", currency="", max_rows=5)

    assert out.status == "not_found"
    assert out.rows == [] and out.summary is None


def test_a_bar_with_no_close_is_skipped() -> None:
    frame = bars(3)
    frame.loc[frame.index[1], "Close"] = math.nan

    out = mapping.history("X", frame, period="1mo", interval="1d", currency="", max_rows=5)

    assert [r.close for r in out.rows] == [100.0, 102.0]


# --- profile -------------------------------------------------------------


def test_a_profile_carries_metrics_as_percentages() -> None:
    info = {
        "longName": "Malayan Banking Berhad",
        "fullExchangeName": "Kuala Lumpur",
        "quoteType": "EQUITY",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "currency": "MYR",
        "longBusinessSummary": "A bank.",
        "marketCap": 126519754752,
        "sharesOutstanding": 12095579217,
        "website": "https://www.maybank.com",
        "trailingPE": 12.02,
        "forwardPE": 11.27,
        "priceToBook": 1.36,
        "priceToSalesTrailing12Months": 4.43,
        "enterpriseToEbitda": None,
        "grossMargins": 0.0,
        "operatingMargins": 0.50157,
        "profitMargins": 0.36702,
        "returnOnEquity": 0.11141,
        "debtToEquity": None,
        "dividendYield": 5.97,
    }

    out = mapping.profile("1155.KL", info)

    assert out.status == "ok"
    assert (out.name, out.exchange, out.kind, out.currency) == (
        "Malayan Banking Berhad",
        "Kuala Lumpur",
        "stock",
        "MYR",
    )
    assert out.metrics.net_margin_pct == 36.702
    assert out.metrics.return_on_equity_pct == 11.141
    assert out.metrics.dividend_yield_pct == 5.97  # Yahoo already reports a percentage
    assert out.metrics.ev_to_ebitda is None
    assert out.crypto is None


def test_a_bare_info_dict_is_not_found() -> None:
    """What yfinance returns for an unknown symbol: `{'trailingPegRatio': None}`."""
    out = mapping.profile("NOPE", {"trailingPegRatio": None})

    assert out.status == "not_found"


def test_a_profile_falls_back_to_the_short_name() -> None:
    assert mapping.profile("X", {"shortName": "X CORP"}).name == "X CORP"


# --- financials ----------------------------------------------------------


def statement_frame() -> pd.DataFrame:
    columns = [pd.Timestamp("2026-06-30"), pd.Timestamp("2026-03-31"), pd.Timestamp("2025-12-31")]
    return pd.DataFrame(
        {
            columns[0]: [109417000000.0, 23434000000.0, math.nan],
            columns[1]: [111184000000.0, 24780000000.0, 1.5],
            columns[2]: [143810000000.0, 36330000000.0, 1.7],
        },
        index=["Total Revenue", "Net Income", "Diluted EPS"],
    )


def test_financials_are_periods_newest_first_with_nans_dropped() -> None:
    out = mapping.financials(
        "AAPL", statement_frame(), statement="income", period="quarterly", currency="USD", limit=2
    )

    assert out.status == "ok"
    assert (out.currency, out.scale) == ("USD", 1)
    assert [p.period_end for p in out.periods] == ["2026-06-30", "2026-03-31"]
    assert out.periods[0].items == {"Total Revenue": 109417000000.0, "Net Income": 23434000000.0}
    assert out.periods[1].items["Diluted EPS"] == 1.5


def test_empty_statements_are_not_found() -> None:
    out = mapping.financials(
        "X", pd.DataFrame(), statement="balance", period="annual", currency="", limit=4
    )

    assert out.status == "not_found"


# --- news ----------------------------------------------------------------


def item(title: str) -> dict:
    return {
        "content": {
            "title": title,
            "pubDate": "2026-05-31T00:02:50Z",
            "provider": {"displayName": "Simply Wall St."},
            "canonicalUrl": {"url": f"https://finance.yahoo.com/{title}"},
        }
    }


def test_news_reads_the_nested_content_and_honours_the_limit() -> None:
    out = mapping.news("1155.KL", [item("a"), item("b"), item("c")], limit=2)

    assert out.status == "ok"
    assert [n.title for n in out.items] == ["a", "b"]
    assert out.items[0].publisher == "Simply Wall St."
    assert out.items[0].published == "2026-05-31T00:02:50Z"
    assert out.items[0].url.endswith("/a")


def test_news_with_nothing_recent_is_ok_and_says_so() -> None:
    out = mapping.news("X", [{"content": {"title": ""}}, {}], limit=5)

    assert out.status == "ok"
    assert out.items == []
    assert "no recent headlines" in out.detail
