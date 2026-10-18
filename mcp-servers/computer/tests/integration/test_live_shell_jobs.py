"""The real computer: a command lost when it stopped is run again and keeps it on no longer."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, TextContent

from computer.jobs import RUNNING_JOBS_SCRIPT
from computer.machine import JOBS_ROOT

pytestmark = pytest.mark.skipif(os.environ.get("COMPUTER_LIVE") != "1", reason="COMPUTER_LIVE=1")

NAME = "cell-harness-computer-shell-test"
COUNTED = {"command": "echo started >> starts; wc -l < starts; sleep 100"}


def text_of(result: CallToolResult) -> str:
    return "\n".join(block.text for block in result.content if isinstance(block, TextContent))


def answer(result: CallToolResult) -> dict:
    assert not result.is_error, text_of(result)
    assert result.structured_content is not None, text_of(result)
    return result.structured_content


def running_jobs() -> list[str]:
    look = ["docker", "exec", NAME, "python3", "-c", RUNNING_JOBS_SCRIPT, JOBS_ROOT]
    return subprocess.run(look, capture_output=True, text=True, check=True).stdout.split()


@pytest.fixture
def params(tmp_path: Path) -> Iterator[StdioServerParameters]:
    (tmp_path / "files").mkdir()
    (tmp_path / "skills").mkdir()
    yield StdioServerParameters(
        command=sys.executable,
        args=["-m", "computer.server"],
        env={
            **os.environ,
            "COMPUTER_NAME": NAME,
            "COMPUTER_FILES_DIR": str(tmp_path / "files"),
            "COMPUTER_SKILLS_DIRS": str(tmp_path / "skills"),
        },
    )
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True, check=False)
    subprocess.run(["docker", "volume", "rm", f"{NAME}-home"], capture_output=True, check=False)


async def test_a_command_the_computer_lost_when_it_stopped_is_run_again(
    params: StdioServerParameters,
) -> None:
    async with Client(params) as client:
        first = answer(await client.call_tool("shell", COUNTED))
        while_running = running_jobs()
        subprocess.run(["docker", "restart", "-t", "1", NAME], capture_output=True, check=True)
        after_restart = running_jobs()
        again = answer(await client.call_tool("shell", COUNTED))

    assert (first["status"], first["output"].strip()) == ("running", "1")
    assert len(while_running) == 1
    assert after_restart == []
    assert (again["status"], again["output"].strip()) == ("running", "2")
