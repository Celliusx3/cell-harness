"""This server as the harness runs it: a real subprocess over stdio.

Proves the two things an in-process client cannot: that `[project.scripts]` and
`main()` agree, and that **nothing is written to stdout** — stdout is the
protocol, so one stray print corrupts a frame.

Hermetic: `PLACES_BASE_URL` points at a port nothing is listening on, and the
test only asks for the tool list, so no request is made.
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import Client, StdioServerParameters


def params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "places.server"],
        env={
            **os.environ,
            "GOOGLE_MAPS_API_KEY": "not-used-by-this-test",
            "PLACES_BASE_URL": "http://127.0.0.1:1/v1",
        },
    )


async def test_it_boots_over_stdio_and_offers_both_tools() -> None:
    async with Client(params()) as client:
        tools = sorted(tool.name for tool in (await client.list_tools()).tools)

    assert tools == ["place_details", "search_text"]


async def test_the_output_schema_survives_the_wire() -> None:
    """`structuredContent` depends on it, and it is the whole reason this
    server exists rather than a third-party one."""
    async with Client(params()) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert tools["search_text"].output_schema is not None
    assert tools["place_details"].output_schema is not None


async def test_it_refuses_to_start_without_a_key() -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "places.server",
        env={k: v for k, v in os.environ.items() if k != "GOOGLE_MAPS_API_KEY"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

    assert process.returncode == 2
    assert b"GOOGLE_MAPS_API_KEY" in stderr
    # The refusal goes to stderr, never stdout.
    assert stdout == b""
