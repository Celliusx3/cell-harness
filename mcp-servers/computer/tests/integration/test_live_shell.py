"""The real computer runs a bot's commands: output, exit code, input, a slow job called again."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, TextContent

pytestmark = pytest.mark.skipif(os.environ.get("COMPUTER_LIVE") != "1", reason="COMPUTER_LIVE=1")

NAME = "cell-harness-computer-shell-test"
MOST_OUTPUT = 10_000


def text_of(result: CallToolResult) -> str:
    return "\n".join(block.text for block in result.content if isinstance(block, TextContent))


def answer(result: CallToolResult) -> dict:
    assert not result.is_error, text_of(result)
    assert result.structured_content is not None, text_of(result)
    return result.structured_content


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path]:
    files, skills = tmp_path / "files", tmp_path / "skills"
    files.mkdir()
    skills.mkdir()
    return files.resolve(), skills.resolve()


@pytest.fixture
def params(folders: tuple[Path, Path]) -> Iterator[StdioServerParameters]:
    files, skills = folders
    yield StdioServerParameters(
        command=sys.executable,
        args=["-m", "computer.server"],
        env={
            **os.environ,
            "COMPUTER_NAME": NAME,
            "COMPUTER_FILES_DIR": str(files),
            "COMPUTER_SKILLS_DIRS": str(skills),
        },
    )
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True, check=False)
    subprocess.run(["docker", "volume", "rm", f"{NAME}-home"], capture_output=True, check=False)


async def test_a_quick_command_answers_its_output_and_exit_code(
    params: StdioServerParameters,
) -> None:
    async with Client(params) as client:
        done = answer(await client.call_tool("shell", {"command": "echo hi; exit 3"}))

    assert (done["status"], done["exit_code"], done["output"].strip()) == ("done", 3, "hi")


async def test_a_slow_command_answers_running_then_its_result_on_the_same_call(
    params: StdioServerParameters,
) -> None:
    call = {"command": "sleep 25; echo finished"}
    async with Client(params) as client:
        first = answer(await client.call_tool("shell", call))
        later = [answer(await client.call_tool("shell", call)) for _ in range(2)]

    assert first["status"] == "running"
    assert first["seconds"] > 0
    finished = [step for step in later if step["status"] == "done"]
    assert finished, later
    assert finished[0]["output"].strip() == "finished"


async def test_the_command_reads_its_input_with_quotes_intact(
    params: StdioServerParameters,
) -> None:
    call = {
        "command": "python3 -c 'import sys; print(sys.stdin.read().upper())'",
        "stdin": 'it\'s "here" $HOME',
    }
    async with Client(params) as client:
        done = answer(await client.call_tool("shell", call))

    assert done["output"].strip() == 'IT\'S "HERE" $HOME'


async def test_a_long_output_keeps_its_end(params: StdioServerParameters) -> None:
    async with Client(params) as client:
        done = answer(await client.call_tool("shell", {"command": "seq 1 200000"}))

    assert done["output"].rstrip().endswith("200000")
    assert len(done["output"]) <= MOST_OUTPUT


async def test_chat_files_are_writable_and_skills_are_not(
    params: StdioServerParameters, folders: tuple[Path, Path]
) -> None:
    files, skills = folders
    (files / "note.txt").write_text("from the Mac")
    async with Client(params) as client:
        read = answer(await client.call_tool("shell", {"command": f"cat {files}/note.txt"}))
        wrote = answer(
            await client.call_tool("shell", {"command": f"echo back > {files}/reply.txt"})
        )
        refused = answer(await client.call_tool("shell", {"command": f"touch {skills}/x"}))

    assert read["output"].strip() == "from the Mac"
    assert wrote["exit_code"] == 0
    assert (files / "reply.txt").read_text().strip() == "back"
    assert refused["exit_code"] != 0
