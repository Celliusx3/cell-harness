"""CoinGecko: the pure mapping, then the client at the transport."""

from __future__ import annotations

import json

import httpx
import pytest

from markets.coingecko import CoinGeckoSource, mapping
from markets.data import RateLimited, Unavailable
from markets.symbol import parse
from tests.conftest import FakeMarket, capturing, http_client

DAY = 86_400_000
T0 = 1_772_150_400_000


def chart(days: int, start: float = 100.0, points_per_day: int = 1) -> dict:
    step = DAY // points_per_day
    prices = [
        [T0 + d * DAY + i * step, start + d + i / 10]
        for d in range(days)
        for i in range(points_per_day)
    ]
    return {"prices": prices, "total_volumes": [[ms, 1000.0 + ms % 7] for ms, _ in prices]}


def market_row(id: str = "bitcoin", **over) -> dict:
    row = {
        "id": id,
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 78902,
        "market_cap": 1584425236631,
        "total_volume": 32825885360,
        "high_24h": 79530,
        "low_24h": 76439,
        "price_change_24h": 1538.93,
        "price_change_percentage_24h": 1.99919,
        "last_updated": "2026-09-14T21:34:20.000Z",
    }
    return row | over


def test_candidates_are_prefixed_and_carry_the_symbol_in_the_name() -> None:
    out = mapping.candidates(
        [{"id": "bitcoin", "name": "Bitcoin", "symbol": "BTC"}, {"name": "no id"}]
    )

    assert [(c.id, c.name, c.kind) for c in out] == [("crypto:bitcoin", "Bitcoin (BTC)", "crypto")]


def test_a_quote_derives_the_previous_close_and_uses_the_source_timestamp() -> None:
    out = mapping.quote("crypto:bitcoin", market_row())

    assert (out.status, out.price, out.currency, out.kind) == ("ok", 78902.0, "USD", "crypto")
    assert out.previous_close == pytest.approx(78902 - 1538.93)
    assert out.change_pct == 1.99919
    assert (out.day_low, out.day_high, out.week52_low) == (76439.0, 79530.0, None)
    assert out.as_of == "2026-09-14T21:34:20.000Z"


def test_a_quote_without_a_price_is_not_found() -> None:
    assert mapping.quote("crypto:x", None).status == "not_found"
    assert mapping.quote("crypto:x", {"current_price": None}).status == "not_found"


def test_a_profile_reads_market_data_in_usd() -> None:
    coin = {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "categories": ["Layer 1 (L1)", None],
        "genesis_date": "2009-01-03",
        "market_cap_rank": 1,
        "description": {"en": "Peer to peer cash."},
        "links": {"homepage": ["http://www.bitcoin.org", ""]},
        "market_data": {
            "market_cap": {"usd": 1584425236631, "myr": 1},
            "circulating_supply": 20084421.0,
            "max_supply": 21000000.0,
            "ath": {"usd": 126080},
            "ath_date": {"usd": "2025-10-06T10:57:42.000Z"},
            "last_updated": "2026-09-14T21:34:40.000Z",
        },
    }

    out = mapping.profile("crypto:bitcoin", coin)

    assert (out.status, out.name, out.currency, out.kind) == ("ok", "Bitcoin", "USD", "crypto")
    assert out.market_cap == 1584425236631.0
    assert out.shares_outstanding == 20084421.0
    assert out.website == "http://www.bitcoin.org"
    assert out.metrics.pe_ttm is None
    assert out.crypto is not None
    assert (out.crypto.symbol, out.crypto.market_cap_rank, out.crypto.ath) == ("BTC", 1, 126080.0)
    assert out.crypto.categories == ["Layer 1 (L1)"]
    assert out.as_of == "2026-09-14T21:34:40.000Z"


def test_daily_history_takes_the_last_point_of_each_utc_day() -> None:
    out = mapping.history(
        "crypto:bitcoin", chart(3, points_per_day=4), period="1mo", interval="1d", max_rows=70
    )

    assert out.status == "ok"
    assert [r.date for r in out.rows] == ["2026-02-27", "2026-02-28", "2026-03-01"]
    assert out.rows[0].close == pytest.approx(100.3)
    assert out.rows[0].open is None and out.rows[0].high is None
    assert out.rows[0].volume is not None
    assert out.currency == "USD"


def test_weekly_and_monthly_bars_are_the_last_day_of_their_bucket() -> None:
    weekly = mapping.history("c", chart(21), period="3mo", interval="1wk", max_rows=70)
    monthly = mapping.history("c", chart(40), period="3mo", interval="1mo", max_rows=70)

    assert [r.date for r in weekly.rows][:2] == ["2026-03-01", "2026-03-08"]
    assert [r.date for r in monthly.rows] == ["2026-02-28", "2026-03-31", "2026-04-07"]


def test_history_truncates_like_yahoo_and_keeps_the_cap_note_first() -> None:
    out = mapping.history(
        "c", chart(10), period="5y", interval="1d", max_rows=4, detail="served as 1y"
    )

    assert out.truncated and len(out.rows) == 4
    assert out.detail.startswith("served as 1y; only the latest 4 of 10")
    assert out.summary is not None and out.summary.first_close == 100.0


def test_an_empty_chart_is_not_found() -> None:
    assert mapping.history("c", {"prices": []}, period="1mo", interval="1d", max_rows=5).status == (
        "not_found"
    )


def routed(*, status: int = 200, body=None):
    def respond(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={"status": {"error_code": status}})
        path = request.url.path
        if path.endswith("/search"):
            return httpx.Response(200, json={"coins": [{"id": "bitcoin", "symbol": "btc"}]})
        if path.endswith("/coins/markets"):
            ids = request.url.params.get("ids")
            return httpx.Response(200, json=[market_row()] if ids == "bitcoin" else [])
        if path.endswith("/coins/bitcoin/market_chart"):
            return httpx.Response(200, json=chart(3))
        if path.endswith("/coins/bitcoin"):
            return httpx.Response(200, json={"id": "bitcoin", "name": "Bitcoin"})
        return httpx.Response(404, json={"error": "coin not found"})

    return capturing(respond if body is None else httpx.Response(200, json=body))


def gecko(handler, headlines: FakeMarket | None = None) -> CoinGeckoSource:
    return CoinGeckoSource(
        api_key="CG-test",
        base_url="https://gecko.test/api/v3/",
        timeout_seconds=5,
        max_rows=70,
        headlines=headlines or FakeMarket("yahoo"),
        client=http_client(handler),
    )


async def test_every_request_carries_the_demo_key_as_a_header_not_a_query() -> None:
    handler, seen = routed()

    await gecko(handler).search("bitcoin")

    assert seen[0].headers["x-cg-demo-api-key"] == "CG-test"
    assert "CG-test" not in str(seen[0].url)
    assert seen[0].url.path == "/api/v3/search"


async def test_a_quote_and_a_profile_route_to_their_endpoints() -> None:
    handler, seen = routed()
    src = gecko(handler)

    quote = await src.quote(parse("crypto:bitcoin"))
    profile = await src.profile(parse("crypto:bitcoin"))

    assert quote.status == "ok" and profile.status == "ok"
    assert seen[0].url.params["vs_currency"] == "usd"
    assert seen[1].url.params["market_data"] == "true"


async def test_an_unknown_coin_is_not_found_on_every_question() -> None:
    handler, _ = routed()
    src = gecko(handler)
    nope = parse("crypto:nope")

    assert (await src.quote(nope)).status == "not_found"
    assert (await src.profile(nope)).status == "not_found"
    assert (await src.history(nope, "1mo", "1d")).status == "not_found"
    assert (await src.news(nope, 3)).status == "not_found"


@pytest.mark.parametrize(("period", "days"), [("1mo", "30"), ("1y", "365"), ("5y", "365")])
async def test_history_asks_for_the_days_of_the_range_capped_at_a_year(
    period: str, days: str
) -> None:
    handler, seen = routed()

    out = await gecko(handler).history(parse("crypto:bitcoin"), period, "1d")

    assert seen[0].url.params["days"] == days
    assert ("served as 1y" in out.detail) == (period == "5y")


async def test_news_goes_through_yahoo_by_the_coin_symbol_and_keeps_the_crypto_id() -> None:
    handler, _ = routed()
    yahoo = FakeMarket("yahoo")

    out = await gecko(handler, headlines=yahoo).news(parse("crypto:bitcoin"), 4)

    assert yahoo.calls == [("news", "crypto:bitcoin", (4,))]
    assert out.id == "crypto:bitcoin"


async def test_news_asks_yahoo_for_the_usd_pair() -> None:
    handler, _ = routed()

    class Spy(FakeMarket):
        async def news(self, symbol, limit):
            self.seen = symbol
            return await super().news(symbol, limit)

    spy = Spy("yahoo")
    await gecko(handler, headlines=spy).news(parse("crypto:bitcoin"), 4)

    assert spy.seen.key == "BTC-USD" and not spy.seen.is_crypto


async def test_statements_are_unsupported_for_a_coin() -> None:
    handler, seen = routed()

    out = await gecko(handler).financials(parse("crypto:bitcoin"), "income", "annual", 4)

    assert out.status == "unsupported"
    assert "get_company_profile" in out.detail
    assert seen == []


async def test_a_429_is_rate_limited() -> None:
    handler, _ = routed(status=429)

    with pytest.raises(RateLimited, match="30/min"):
        await gecko(handler).search("x")


@pytest.mark.parametrize("status", [401, 403])
async def test_a_rejected_key_names_the_variable(status: int) -> None:
    handler, _ = routed(status=status)

    with pytest.raises(Unavailable, match="COINGECKO_API_KEY"):
        await gecko(handler).search("x")


async def test_any_other_status_is_unavailable() -> None:
    handler, _ = routed(status=502)

    with pytest.raises(Unavailable, match="HTTP 502"):
        await gecko(handler).search("x")


async def test_a_dead_network_is_unavailable() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns")

    with pytest.raises(Unavailable, match="could not be reached"):
        await gecko(boom).search("x")


async def test_non_json_is_unavailable() -> None:
    handler, _ = capturing(httpx.Response(200, text="<html>"))

    with pytest.raises(Unavailable, match="not JSON"):
        await gecko(handler).search("x")


def test_the_market_row_fixture_matches_the_recorded_shape() -> None:
    assert set(json.loads(json.dumps(market_row()))) >= {"current_price", "last_updated"}
