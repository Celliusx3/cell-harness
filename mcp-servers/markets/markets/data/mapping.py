"""yfinance's shapes into ours. Pure functions, so the whole translation is
unit-tested with hand-built frames and never touches Yahoo.

The shapes were read from live calls on 2026-09-14 (yfinance 1.7.0):
`Search.quotes` dicts, `Ticker.fast_info` keys, `history()` frames indexed by
tz-aware timestamp, statement frames with line items as the index and period
ends as columns, and `Ticker.news` items nested under `content`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from markets.models import (
    YAHOO,
    Bar,
    Candidate,
    Financials,
    FiscalPeriod,
    History,
    Interval,
    Kind,
    Metrics,
    News,
    NewsItem,
    Period,
    Profile,
    Quote,
    Range,
    Statement,
    Summary,
    now_iso,
)

# Yahoo's quoteType, and the ones we hand to the model. Futures, options,
# indices and mutual funds are dropped from search: nothing else here can do
# anything with them, and a candidate the model cannot use is a wrong turn.
_KINDS: dict[str, Kind] = {"EQUITY": "stock", "ETF": "etf"}

# The interval to suggest when a range does not fit the row cap at the one asked.
_COARSER: dict[Interval, Interval | None] = {"1d": "1wk", "1wk": "1mo", "1mo": None}


def candidates(quotes: Sequence[Mapping[str, Any]]) -> list[Candidate]:
    out: list[Candidate] = []
    for q in quotes:
        kind = _KINDS.get(str(q.get("quoteType", "")))
        symbol = str(q.get("symbol", "")).strip()
        if kind is None or not symbol:
            continue
        out.append(
            Candidate(
                id=symbol,
                name=str(q.get("longname") or q.get("shortname") or symbol),
                exchange=str(q.get("exchDisp") or q.get("exchange") or ""),
                kind=kind,
            )
        )
    return out


def quote(id: str, fast: Mapping[str, Any]) -> Quote:
    price = _num(fast.get("lastPrice"))
    if price is None:
        return Quote(
            id=id,
            status="not_found",
            detail="Yahoo has no price for this symbol; check it with search_symbol",
            as_of=now_iso(),
            source=YAHOO,
        )
    previous = _num(fast.get("previousClose"))
    change = None if not previous else round((price / previous - 1) * 100, 4)
    return Quote(
        id=id,
        status="ok",
        kind=_KINDS.get(str(fast.get("quoteType", ""))),
        price=price,
        previous_close=previous,
        change_pct=change,
        day_low=_num(fast.get("dayLow")),
        day_high=_num(fast.get("dayHigh")),
        week52_low=_num(fast.get("yearLow")),
        week52_high=_num(fast.get("yearHigh")),
        market_cap=_num(fast.get("marketCap")),
        volume=_num(fast.get("lastVolume")),
        currency=str(fast.get("currency") or ""),
        exchange=str(fast.get("exchange") or ""),
        as_of=now_iso(),
        source=YAHOO,
    )


def history(
    id: str,
    frame: pd.DataFrame,
    *,
    period: Range,
    interval: Interval,
    currency: str,
    max_rows: int,
) -> History:
    base = dict(id=id, period=period, interval=interval, currency=currency, source=YAHOO)
    if frame is None or frame.empty:
        return History(
            status="not_found",
            detail="Yahoo returned no bars; the symbol may be wrong or delisted",
            as_of=now_iso(),
            **base,
        )
    closes = frame["Close"].dropna()
    rows = [
        Bar(
            date=ts.strftime("%Y-%m-%d"),
            open=_num(r.get("Open")),
            high=_num(r.get("High")),
            low=_num(r.get("Low")),
            close=round(float(r["Close"]), 6),
            volume=_num(r.get("Volume")),
        )
        for ts, r in frame.iterrows()
        if not _is_nan(r["Close"])
    ]
    return History(
        status="ok",
        detail=truncation_note(len(rows), max_rows, interval),
        truncated=len(rows) > max_rows,
        # Summary spans the whole range even when rows are cut: the number the
        # model most often wants is "how did it do over the period", and that
        # must not silently become "over the rows that fit".
        summary=Summary(
            first_close=round(float(closes.iloc[0]), 6),
            last_close=round(float(closes.iloc[-1]), 6),
            high=round(float(frame["High"].max() if "High" in frame else closes.max()), 6),
            low=round(float(frame["Low"].min() if "Low" in frame else closes.min()), 6),
            change_pct=round((float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 4),
        ),
        rows=rows[-max_rows:],
        as_of=now_iso(),
        **base,
    )


def truncation_note(count: int, max_rows: int, interval: Interval) -> str:
    if count <= max_rows:
        return ""
    coarser = _COARSER[interval]
    hint = f"; ask for interval {coarser} to see the whole range" if coarser else ""
    return f"only the latest {max_rows} of {count} bars are returned{hint}"


def profile(id: str, info: Mapping[str, Any]) -> Profile:
    name = info.get("longName") or info.get("shortName")
    if not name:
        return Profile(
            id=id,
            status="not_found",
            detail="Yahoo has no profile for this symbol; check it with search_symbol",
            as_of=now_iso(),
            source=YAHOO,
        )
    return Profile(
        id=id,
        status="ok",
        kind=_KINDS.get(str(info.get("quoteType", ""))),
        name=str(name),
        exchange=str(info.get("fullExchangeName") or info.get("exchange") or ""),
        sector=str(info.get("sector") or ""),
        industry=str(info.get("industry") or ""),
        currency=str(info.get("currency") or ""),
        description=str(info.get("longBusinessSummary") or ""),
        market_cap=_num(info.get("marketCap")),
        shares_outstanding=_num(info.get("sharesOutstanding")),
        website=str(info.get("website") or ""),
        metrics=Metrics(
            pe_ttm=_num(info.get("trailingPE")),
            forward_pe=_num(info.get("forwardPE")),
            price_to_book=_num(info.get("priceToBook")),
            price_to_sales_ttm=_num(info.get("priceToSalesTrailing12Months")),
            ev_to_ebitda=_num(info.get("enterpriseToEbitda")),
            gross_margin_pct=_pct(info.get("grossMargins")),
            operating_margin_pct=_pct(info.get("operatingMargins")),
            net_margin_pct=_pct(info.get("profitMargins")),
            return_on_equity_pct=_pct(info.get("returnOnEquity")),
            # Yahoo already reports these two as percentages.
            debt_to_equity_pct=_num(info.get("debtToEquity")),
            dividend_yield_pct=_num(info.get("dividendYield")),
        ),
        as_of=now_iso(),
        source=YAHOO,
    )


def financials(
    id: str,
    frame: pd.DataFrame,
    *,
    statement: Statement,
    period: FiscalPeriod,
    currency: str,
    limit: int,
) -> Financials:
    base = dict(id=id, statement=statement, period=period, currency=currency, source=YAHOO)
    if frame is None or frame.empty:
        return Financials(
            status="not_found",
            detail="Yahoo has no statements for this symbol",
            as_of=now_iso(),
            **base,
        )
    periods = [
        Period(
            period_end=pd.Timestamp(col).strftime("%Y-%m-%d"),
            items={str(line): float(v) for line, v in frame[col].items() if not _is_nan(v)},
        )
        for col in list(frame.columns)[:limit]
    ]
    return Financials(status="ok", periods=periods, as_of=now_iso(), **base)


def news(id: str, items: Sequence[Mapping[str, Any]], limit: int) -> News:
    out: list[NewsItem] = []
    for item in items[:limit]:
        content = item.get("content") or {}
        title = str(content.get("title") or "").strip()
        if not title:
            continue
        out.append(
            NewsItem(
                title=title,
                publisher=str((content.get("provider") or {}).get("displayName") or ""),
                published=str(content.get("pubDate") or ""),
                url=str((content.get("canonicalUrl") or {}).get("url") or ""),
            )
        )
    return News(
        id=id,
        status="ok",
        detail="" if out else "Yahoo has no recent headlines for this symbol",
        items=out,
        as_of=now_iso(),
        source=YAHOO,
    )


def _is_nan(value: Any) -> bool:
    try:
        return value is None or math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def _num(value: Any) -> float | None:
    # Yahoo hands back float32 noise (10.460000038146973 for a 10.46 print);
    # six decimals is finer than any quoted price and drops the noise.
    return None if _is_nan(value) else round(float(value), 6)


def _pct(value: Any) -> float | None:
    number = _num(value)
    return None if number is None else round(number * 100, 4)
