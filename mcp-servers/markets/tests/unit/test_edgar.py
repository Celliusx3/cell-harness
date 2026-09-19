"""EDGAR at the transport."""

from __future__ import annotations

import httpx
import pytest

from markets.data import RateLimited, Unavailable
from markets.edgar import EdgarClient
from markets.symbol import parse
from tests.conftest import capturing, http_client

TICKERS = {
    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "2": {"cik_str": 1, "title": "no ticker"},
}

SUBMISSIONS = {
    "cik": "0000320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "accessionNumber": [
                "0001140361-26-036226",
                "0000320193-26-000020",
                "0000320193-26-000013",
            ],
            "filingDate": ["2026-09-10", "2026-07-31", "2026-05-01"],
            "reportDate": ["2026-09-08", "2026-06-27", "2026-03-28"],
            "form": ["4", "10-Q", "10-Q"],
            "primaryDocument": ["xslF345X06/form4.xml", "aapl-20260627.htm", "aapl-20260328.htm"],
            "primaryDocDescription": ["FORM 4", "10-Q"],
        }
    },
}


def routed(*, status: int = 200):
    def respond(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, text="denied")
        if request.url.host == "www.sec.test" and request.url.path == "/files/company_tickers.json":
            return httpx.Response(200, json=TICKERS)
        if request.url.host == "data.sec.test" and request.url.path.startswith("/submissions/"):
            return httpx.Response(200, json=SUBMISSIONS)
        return httpx.Response(404)

    return capturing(respond)


def edgar(handler) -> EdgarClient:
    return EdgarClient(
        user_agent="tests tests@example.com",
        data_url="https://data.sec.test/",
        www_url="https://www.sec.test",
        timeout_seconds=5,
        client=http_client(handler),
    )


async def test_filings_carry_a_document_url_and_the_declared_user_agent() -> None:
    handler, seen = routed()

    out = await edgar(handler).filings(parse("AAPL"), None, 10)

    assert out.status == "ok"
    assert (out.cik, out.company) == ("320193", "Apple Inc.")
    assert [f.form for f in out.filings] == ["4", "10-Q", "10-Q"]
    assert out.filings[1].url == (
        "https://www.sec.test/Archives/edgar/data/320193/000032019326000020/aapl-20260627.htm"
    )
    assert out.filings[1].period_of_report == "2026-06-27"
    assert out.filings[2].description == ""
    assert all(r.headers["User-Agent"] == "tests tests@example.com" for r in seen)
    assert seen[1].url.path == "/submissions/CIK0000320193.json"


async def test_the_form_filter_is_exact_and_case_insensitive_and_the_limit_applies() -> None:
    handler, _ = routed()

    out = await edgar(handler).filings(parse("AAPL"), "10-q", 1)

    assert [(f.form, f.filed) for f in out.filings] == [("10-Q", "2026-07-31")]


async def test_the_cik_map_is_fetched_once_per_process() -> None:
    handler, seen = routed()
    client = edgar(handler)

    await client.filings(parse("AAPL"), None, 1)
    await client.filings(parse("NVDA"), None, 1)

    assert [r.url.path for r in seen].count("/files/company_tickers.json") == 1


async def test_a_ticker_edgar_does_not_know_is_not_found() -> None:
    handler, seen = routed()

    out = await edgar(handler).filings(parse("ZZZZ"), None, 5)

    assert out.status == "not_found"
    assert len(seen) == 1


@pytest.mark.parametrize("raw", ["1155.KL", "crypto:bitcoin"])
async def test_non_us_ids_are_unsupported_without_a_request(raw: str) -> None:
    handler, seen = routed()

    out = await edgar(handler).filings(parse(raw), None, 5)

    assert out.status == "unsupported"
    assert "US listings only" in out.detail
    assert seen == []


async def test_a_403_names_the_user_agent_setting() -> None:
    handler, _ = routed(status=403)

    with pytest.raises(Unavailable, match="SEC_USER_AGENT"):
        await edgar(handler).filings(parse("AAPL"), None, 5)


async def test_a_429_is_rate_limited() -> None:
    handler, _ = routed(status=429)

    with pytest.raises(RateLimited):
        await edgar(handler).filings(parse("AAPL"), None, 5)


async def test_any_other_status_and_a_dead_network_are_unavailable() -> None:
    handler, _ = routed(status=500)
    with pytest.raises(Unavailable, match="HTTP 500"):
        await edgar(handler).filings(parse("AAPL"), None, 5)

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns")

    with pytest.raises(Unavailable, match="could not be reached"):
        await edgar(boom).filings(parse("AAPL"), None, 5)


async def test_non_json_is_unavailable() -> None:
    handler, _ = capturing(httpx.Response(200, text="<html>"))

    with pytest.raises(Unavailable, match="not JSON"):
        await edgar(handler).filings(parse("AAPL"), None, 5)
