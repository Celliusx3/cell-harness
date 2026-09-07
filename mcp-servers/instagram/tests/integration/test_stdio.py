"""This server as the harness actually runs it: a real subprocess over stdio.

Two things only this test can prove, and both have bitten real MCP servers:

- **Nothing is written to stdout.** stdout *is* the protocol, so a stray `print`
  or a library's banner corrupts a JSON-RPC frame. An in-process `Client` shares
  the interpreter and would never notice.
- **The declared entry point actually starts.** `pyproject`'s `[project.scripts]`
  and `main()` agreeing is not something an import can check.

Hermetic despite being a subprocess: the fixture media backend means no
Instagram, and asking only for an unfetched reel means no provider call.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

FIXTURES = Path(__file__).parent.parent / "fixtures" / "media"

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="this server refuses to start without ffmpeg"
)


def params(work_dir: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "instagram.server"],
        env={
            **os.environ,
            "INSTAGRAM_MEDIA_BACKEND": "fixture",
            "INSTAGRAM_FIXTURE_ROOT": str(FIXTURES),
            "AI_PROVIDER_BASE_URL": "https://provider.invalid/v1",
            "AI_PROVIDER_API_KEY": "not-used-by-this-test",
            "INSTAGRAM_WORK_DIR": str(work_dir),
        },
    )


async def test_it_boots_over_stdio_and_offers_both_tools(tmp_path: Path) -> None:
    async with Client(params(tmp_path / "work")) as client:
        tools = sorted(tool.name for tool in (await client.list_tools()).tools)

    assert tools == ["fetch_reels", "read_reels"]


async def test_a_call_round_trips_over_the_real_wire(tmp_path: Path) -> None:
    """`structured_content` surviving a subprocess boundary is the property the
    harness's code-mode bridge depends on."""
    async with Client(params(tmp_path / "work")) as client:
        result = await client.call_tool("read_reels", {"shortcodes": ["OKvideo000"], "want": []})

    assert result.structured_content is not None
    item = result.structured_content["items"][0]
    assert item["status"] == "not_fetched"


async def test_fetching_from_the_fixture_backend_works_end_to_end(tmp_path: Path) -> None:
    async with Client(params(tmp_path / "work")) as client:
        result = await client.call_tool(
            "fetch_reels", {"urls": ["https://www.instagram.com/reel/OKvideo000/?igsh=x"]}
        )

    item = result.structured_content["items"][0]
    assert item["status"] == "ok"
    assert item["mentions"] == ["warung.mak.cik"]


async def test_it_refuses_to_start_without_a_provider_key(tmp_path: Path) -> None:
    """A server that dies at startup is absent from `list_functions`, so the
    model learns it has no Instagram capability instead of retrying a broken tool."""
    import asyncio

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "instagram.server",
        env={
            **os.environ,
            "INSTAGRAM_MEDIA_BACKEND": "fixture",
            "INSTAGRAM_FIXTURE_ROOT": str(FIXTURES),
            "AI_PROVIDER_BASE_URL": "https://provider.invalid/v1",
            "AI_PROVIDER_API_KEY": "",
        },
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

    assert process.returncode == 2
    assert b"AI_PROVIDER_API_KEY" in stderr
    # The refusal goes to stderr, never stdout — stdout is the protocol.
    assert stdout == b""
