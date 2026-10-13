"""This server as the harness runs it: a real subprocess over stdio."""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import Client, StdioServerParameters

UNUSED_NAME = "cell-harness-computer-stdio-test"
BROWSER_TOOLS = ("browser_act", "browser_navigate", "browser_read_page")
APP_ONLY_TOOLS = (
    "file_download",
    "file_list",
    "file_read",
    "file_upload",
    "keep_awake",
    "release_control",
    "screen_session",
    "screenshot",
    "terminal_session",
)


def params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "computer.server"],
        env={**os.environ, "COMPUTER_NAME": UNUSED_NAME},
    )


async def test_it_boots_over_stdio_and_offers_exactly_the_twelve_tools() -> None:
    async with Client(params()) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert sorted(tools) == sorted([*BROWSER_TOOLS, *APP_ONLY_TOOLS])
    assert all(tools[name].output_schema is not None for name in BROWSER_TOOLS)


async def test_it_refuses_to_start_with_an_unusable_idle_time() -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "computer.server",
        env={**os.environ, "COMPUTER_IDLE_MINUTES": "0"},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

    assert process.returncode == 2
    assert b"COMPUTER_IDLE_MINUTES" in stderr
    assert stdout == b""
