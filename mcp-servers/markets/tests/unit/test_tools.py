"""The tools through a real MCP client, in-process."""

from __future__ import annotations

import httpx
import pytest
from mcp import Client

from markets.data import RateLimited, Unavailable
from markets.models import Candidate
from tests.conftest import FakeMarket, ok_quote, server_with

TOOLS = {
    "search_symbol",
    "get_quote",
    "get_price_history",
    "get_company_profile",
    "get_financials",
    "get_filings",
    "get_news",
}


async def call(server, tool: str, args: dict):
    async with Client(server) as client:
        return await client.call_tool(tool, args)


def error_text(result) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


async def test_all_seven_tools_declare_an_output_schema() -> None:
    async with Client(server_with()) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == TOOLS
    assert all(tool.output_schema is not None for tool in tools.values())


def stock(id: str, kind: str = "stock") -> Candidate:
    return Candidate(id=id, name=id, exchange="X", kind=kind)


async def test_search_merges_both_sources_and_names_them() -> None:
    yahoo, gecko = FakeMarket("yahoo"), FakeMarket("gecko")
    yahoo.candidates = [stock("1155.KL"), stock("SPY", "etf")]
    gecko.candidates = [stock("crypto:bitcoin", "crypto")]

    result = await call(server_with(market=yahoo, crypto=gecko), "search_symbol", {"query": " x "})

    data = result.structured_content
    assert [c["id"] for c in data["candidates"]] == ["1155.KL", "SPY", "crypto:bitcoin"]
    assert data["query_sent"] == "x"
    assert data["source"] == "yahoo, gecko"
    assert yahoo.calls == [("search", "x", ())]


@pytest.mark.parametrize(
    ("kind", "expected", "asked"),
    [
        ("etf", ["SPY"], {"yahoo"}),
        ("stock", ["1155.KL"], {"yahoo"}),
        ("crypto", ["crypto:b"], {"gecko"}),
    ],
)
async def test_kind_filters_candidates_and_skips_the_other_source(
    kind: str, expected: list[str], asked: set[str]
) -> None:
    yahoo, gecko = FakeMarket("yahoo"), FakeMarket("gecko")
    yahoo.candidates = [stock("1155.KL"), stock("SPY", "etf")]
    gecko.candidates = [stock("crypto:b", "crypto")]

    result = await call(
        server_with(market=yahoo, crypto=gecko), "search_symbol", {"query": "x", "kind": kind}
    )

    assert [c["id"] for c in result.structured_content["candidates"]] == expected
    assert {s.name for s in (yahoo, gecko) if s.calls} == asked


async def test_one_source_down_does_not_sink_the_other_and_is_noted() -> None:
    yahoo, gecko = FakeMarket("yahoo"), FakeMarket("gecko")
    yahoo.candidates = [stock("AAPL")]
    gecko.candidates = Unavailable("dns")

    result = await call(server_with(market=yahoo, crypto=gecko), "search_symbol", {"query": "x"})

    assert not result.is_error
    assert [c["id"] for c in result.structured_content["candidates"]] == ["AAPL"]
    assert "gecko was unavailable: dns" in result.structured_content["detail"]


async def test_both_sources_down_is_a_whole_call_failure() -> None:
    yahoo, gecko = FakeMarket("yahoo"), FakeMarket("gecko")
    yahoo.candidates = Unavailable("a")
    gecko.candidates = RateLimited("b")

    result = await call(server_with(market=yahoo, crypto=gecko), "search_symbol", {"query": "x"})

    assert result.is_error
    assert "yahoo was unavailable: a" in error_text(result)


async def test_no_match_is_advice_not_an_error() -> None:
    result = await call(server_with(), "search_symbol", {"query": "zzz"})

    assert not result.is_error
    assert result.structured_content["candidates"] == []
    assert "shorter query" in result.structured_content["detail"]


async def test_an_empty_query_is_refused() -> None:
    result = await call(server_with(), "search_symbol", {"query": "  "})

    assert result.is_error


async def test_quotes_route_by_id_and_come_back_in_order() -> None:
    yahoo, gecko = FakeMarket("yahoo"), FakeMarket("gecko")
    yahoo.quotes["AAPL"] = ok_quote("AAPL", 333.0)
    gecko.quotes["crypto:bitcoin"] = ok_quote("crypto:bitcoin", 78902.0)

    result = await call(
        server_with(market=yahoo, crypto=gecko),
        "get_quote",
        {"ids": ["crypto:bitcoin", "aapl", "NOPE"]},
    )

    items = result.structured_content["items"]
    assert [(i["id"], i["status"]) for i in items] == [
        ("crypto:bitcoin", "ok"),
        ("AAPL", "ok"),
        ("NOPE", "not_found"),
    ]
    assert items[0]["price"] == 78902.0
    assert gecko.calls == [("quote", "crypto:bitcoin", ())]


async def test_a_bad_id_and_a_dead_source_are_per_item_errors() -> None:
    yahoo = FakeMarket("yahoo")
    yahoo.quotes["AAPL"] = ok_quote("AAPL")
    yahoo.quotes["MSFT"] = Unavailable("Yahoo Finance could not be read")

    result = await call(
        server_with(market=yahoo), "get_quote", {"ids": ["AAPL", "crypto:", "MSFT"]}
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [i["status"] for i in items] == ["ok", "error", "error"]
    assert "crypto:bitcoin" in items[1]["detail"]
    assert "Yahoo Finance" in items[2]["detail"]


async def test_a_slow_id_is_a_timeout_and_the_fast_one_survives() -> None:
    yahoo = FakeMarket("yahoo")
    yahoo.quotes["AAPL"] = ok_quote("AAPL")
    yahoo.quotes["SLOW"] = ok_quote("SLOW")
    yahoo.delay["SLOW"] = 5

    result = await call(
        server_with(market=yahoo, call_budget_seconds=0.2),
        "get_quote",
        {"ids": ["AAPL", "SLOW"]},
    )

    items = result.structured_content["items"]
    assert [i["status"] for i in items] == ["ok", "timeout"]
    assert "ask again" in items[1]["detail"]


async def test_too_many_ids_is_refused_with_the_cap() -> None:
    result = await call(server_with(max_ids=2), "get_quote", {"ids": ["A", "B", "C"]})

    assert result.is_error
    assert "at most 2 ids" in error_text(result)


async def test_no_ids_is_refused() -> None:
    assert (await call(server_with(), "get_quote", {"ids": []})).is_error


async def test_history_defaults_to_three_months_of_daily_bars() -> None:
    yahoo = FakeMarket("yahoo")

    result = await call(server_with(market=yahoo), "get_price_history", {"id": "1155.kl"})

    assert yahoo.calls == [("history", "1155.KL", ("3mo", "1d"))]
    assert result.structured_content["period"] == "3mo"


async def test_a_profile_routes_a_coin_to_the_crypto_source() -> None:
    gecko = FakeMarket("gecko")

    result = await call(server_with(crypto=gecko), "get_company_profile", {"id": "crypto:bitcoin"})

    assert gecko.calls == [("profile", "crypto:bitcoin", ())]
    assert result.structured_content["name"] == "Fake Co"


@pytest.mark.parametrize(("asked", "given"), [(0, 1), (3, 3), (99, 8)])
async def test_financials_clamp_the_period_count(asked: int, given: int) -> None:
    yahoo = FakeMarket("yahoo")

    await call(
        server_with(market=yahoo),
        "get_financials",
        {"id": "AAPL", "statement": "income", "period": "quarterly", "limit": asked},
    )

    assert yahoo.calls == [("financials", "AAPL", ("income", "quarterly", given))]


async def test_news_clamps_its_limit_and_defaults_to_eight() -> None:
    yahoo = FakeMarket("yahoo")

    await call(server_with(market=yahoo), "get_news", {"id": "AAPL"})
    await call(server_with(market=yahoo), "get_news", {"id": "AAPL", "limit": 500})

    assert [c[2] for c in yahoo.calls] == [(8,), (20,)]


async def test_filings_go_to_edgar_and_a_non_us_id_is_unsupported() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected for a .KL id")

    result = await call(server_with(edgar_handler=respond), "get_filings", {"id": "1155.KL"})

    assert not result.is_error
    assert result.structured_content["status"] == "unsupported"


async def test_an_unreachable_edgar_is_a_whole_call_failure_that_names_it() -> None:
    result = await call(
        server_with(edgar_handler=lambda r: httpx.Response(403)), "get_filings", {"id": "AAPL"}
    )

    assert result.is_error
    assert "SEC_USER_AGENT" in error_text(result)


async def test_a_malformed_id_on_a_single_id_tool_is_refused_with_the_shape() -> None:
    result = await call(server_with(), "get_company_profile", {"id": "crypto:"})

    assert result.is_error
    assert "crypto:bitcoin" in error_text(result)


async def test_a_rate_limited_source_on_a_single_id_tool_fails_the_call() -> None:
    class Limited(FakeMarket):
        async def profile(self, symbol):
            raise RateLimited("Yahoo Finance rate-limited the request")

    result = await call(server_with(market=Limited("yahoo")), "get_company_profile", {"id": "A"})

    assert result.is_error
    assert "rate-limited" in error_text(result)
