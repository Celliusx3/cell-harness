"""This server as the harness runs it: a real subprocess over stdio."""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import Client, StdioServerParameters

ENV = {
    "SEC_USER_AGENT": "tests tests@example.com",
    "COINGECKO_API_KEY": "not-used-by-this-test",
    "MARKETS_EDGAR_DATA_URL": "http://127.0.0.1:1",
    "MARKETS_EDGAR_WWW_URL": "http://127.0.0.1:1",
    "MARKETS_COINGECKO_BASE_URL": "http://127.0.0.1:1/api/v3",
}


def params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable, args=["-m", "markets.server"], env={**os.environ, **ENV}
    )


async def test_it_boots_over_stdio_and_offers_seven_tools() -> None:
    async with Client(params()) as client:
        tools = sorted(tool.name for tool in (await client.list_tools()).tools)

    assert tools == [
        "get_company_profile",
        "get_filings",
        "get_financials",
        "get_news",
        "get_price_history",
        "get_quote",
        "search_symbol",
    ]


async def test_every_output_schema_survives_the_wire() -> None:
    async with Client(params()) as client:
        tools = (await client.list_tools()).tools

    assert all(tool.output_schema is not None for tool in tools)


async def test_it_refuses_to_start_without_a_user_agent() -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "markets.server",
        env={k: v for k, v in {**os.environ, **ENV}.items() if k != "SEC_USER_AGENT"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

    assert process.returncode == 2
    assert b"SEC_USER_AGENT" in stderr
    assert stdout == b""
