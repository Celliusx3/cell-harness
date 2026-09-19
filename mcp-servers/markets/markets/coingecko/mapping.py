"""CoinGecko's shapes into ours."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from markets.data.mapping import truncation_note
from markets.models import (
    COINGECKO,
    Bar,
    Candidate,
    CryptoFacts,
    History,
    Interval,
    Profile,
    Quote,
    Range,
    Summary,
    now_iso,
)
from markets.symbol import CRYPTO_PREFIX

VS = "usd"


def candidates(coins: Sequence[Mapping[str, Any]]) -> list[Candidate]:
    out: list[Candidate] = []
    for coin in coins:
        coin_id = str(coin.get("id") or "").strip()
        if not coin_id:
            continue
        symbol = str(coin.get("symbol") or "").upper()
        name = str(coin.get("name") or coin_id)
        out.append(
            Candidate(
                id=f"{CRYPTO_PREFIX}{coin_id}",
                name=f"{name} ({symbol})" if symbol else name,
                exchange="",
                kind="crypto",
            )
        )
    return out


def quote(id: str, market: Mapping[str, Any] | None) -> Quote:
    if not market or market.get("current_price") is None:
        return Quote(
            id=id,
            status="not_found",
            detail="CoinGecko has no market data for this id; find it with search_symbol",
            as_of=now_iso(),
            source=COINGECKO,
        )
    price = float(market["current_price"])
    change = _num(market.get("price_change_24h"))
    return Quote(
        id=id,
        status="ok",
        kind="crypto",
        price=price,
        previous_close=None if change is None else round(price - change, 8),
        change_pct=_num(market.get("price_change_percentage_24h")),
        day_low=_num(market.get("low_24h")),
        day_high=_num(market.get("high_24h")),
        market_cap=_num(market.get("market_cap")),
        volume=_num(market.get("total_volume")),
        currency=VS.upper(),
        exchange="",
        as_of=str(market.get("last_updated") or now_iso()),
        source=COINGECKO,
    )


def profile(id: str, coin: Mapping[str, Any]) -> Profile:
    data = coin.get("market_data") or {}
    return Profile(
        id=id,
        status="ok",
        kind="crypto",
        name=str(coin.get("name") or id),
        currency=VS.upper(),
        description=str((coin.get("description") or {}).get("en") or ""),
        market_cap=_in_vs(data.get("market_cap")),
        shares_outstanding=_num(data.get("circulating_supply")),
        website=str(next(iter(coin.get("links", {}).get("homepage") or []), "") or ""),
        crypto=CryptoFacts(
            symbol=str(coin.get("symbol") or "").upper(),
            market_cap_rank=_int(coin.get("market_cap_rank")),
            circulating_supply=_num(data.get("circulating_supply")),
            max_supply=_num(data.get("max_supply")),
            ath=_in_vs(data.get("ath")),
            ath_date=str((data.get("ath_date") or {}).get(VS) or ""),
            genesis_date=str(coin.get("genesis_date") or ""),
            categories=[str(c) for c in coin.get("categories") or [] if c],
        ),
        as_of=str(data.get("last_updated") or now_iso()),
        source=COINGECKO,
    )


def history(
    id: str,
    chart: Mapping[str, Any],
    *,
    period: Range,
    interval: Interval,
    max_rows: int,
    detail: str = "",
) -> History:
    base = dict(id=id, period=period, interval=interval, currency=VS.upper(), source=COINGECKO)
    daily = _daily(chart.get("prices") or [], chart.get("total_volumes") or [])
    if not daily:
        return History(
            status="not_found",
            detail="CoinGecko returned no prices for this id",
            as_of=now_iso(),
            **base,
        )
    rows = _bucket(daily, interval)
    closes = [close for _, close, _ in daily]
    notes = [n for n in (detail, truncation_note(len(rows), max_rows, interval)) if n]
    return History(
        status="ok",
        detail="; ".join(notes),
        truncated=len(rows) > max_rows,
        summary=Summary(
            first_close=closes[0],
            last_close=closes[-1],
            high=max(closes),
            low=min(closes),
            change_pct=round((closes[-1] / closes[0] - 1) * 100, 4),
        ),
        rows=rows[-max_rows:],
        as_of=now_iso(),
        **base,
    )


def _daily(
    prices: Sequence[Sequence[float]], volumes: Sequence[Sequence[float]]
) -> list[tuple[str, float, float | None]]:
    """(date, last price that day, last volume that day), ascending."""
    volume_by_ms = {int(ms): float(v) for ms, v in volumes}
    by_day: dict[str, tuple[float, float | None]] = {}
    for ms, price in prices:
        day = datetime.fromtimestamp(int(ms) / 1000, tz=UTC).strftime("%Y-%m-%d")
        by_day[day] = (float(price), volume_by_ms.get(int(ms)))
    return [(day, close, volume) for day, (close, volume) in sorted(by_day.items())]


def _bucket(daily: list[tuple[str, float, float | None]], interval: Interval) -> list[Bar]:
    if interval == "1d":
        return [Bar(date=d, close=c, volume=v) for d, c, v in daily]
    last: dict[str, tuple[str, float, float | None]] = {}
    for day, close, volume in daily:
        key = _bucket_key(day, interval)
        last[key] = (day, close, volume)
    return [Bar(date=d, close=c, volume=v) for d, c, v in last.values()]


def _bucket_key(day: str, interval: Interval) -> str:
    if interval == "1mo":
        return day[:7]
    year, week, _ = datetime.strptime(day, "%Y-%m-%d").isocalendar()
    return f"{year}-W{week:02d}"


def _in_vs(per_currency: Any) -> float | None:
    return _num(per_currency.get(VS)) if isinstance(per_currency, Mapping) else None


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _num(value)
    return None if number is None else int(number)
