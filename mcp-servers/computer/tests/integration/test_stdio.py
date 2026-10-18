"""This server as the harness runs it: a real subprocess over stdio."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from tests.fake_host_service import EXIT_CODE, declaring, fake_host_service, write_skill

UNUSED_NAME = "cell-harness-computer-stdio-test"
MODEL_TOOLS = ("browser_act", "browser_navigate", "browser_read_page", "shell")
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


def environment(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "files").mkdir()
    (tmp_path / "skills").mkdir()
    return {
        **os.environ,
        "COMPUTER_NAME": UNUSED_NAME,
        "COMPUTER_FILES_DIR": str(tmp_path / "files"),
        "COMPUTER_SKILLS_DIRS": str(tmp_path / "skills"),
    }


def params(tmp_path: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable, args=["-m", "computer.server"], env=environment(tmp_path)
    )


async def test_it_boots_over_stdio_and_offers_exactly_the_thirteen_tools(tmp_path: Path) -> None:
    async with Client(params(tmp_path)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert sorted(tools) == sorted([*MODEL_TOOLS, *APP_ONLY_TOOLS])
    assert all(tools[name].output_schema is not None for name in MODEL_TOOLS)


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


async def test_it_starts_without_a_declared_program_that_does_not_listen(tmp_path: Path) -> None:
    env = environment(tmp_path)
    program = fake_host_service(tmp_path / "bin", "exits")
    write_skill(
        tmp_path / "skills",
        "comic",
        declaring(f"{program} --port {{port}} --token-file {{token_file}}"),
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "computer.server",
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

    assert process.returncode == 0
    warning = f"run without it: {program} exited with code {EXIT_CODE}"
    assert warning.encode() in stderr
    assert stdout == b""
