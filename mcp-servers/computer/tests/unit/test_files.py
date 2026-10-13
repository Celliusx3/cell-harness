"""file_list, file_read, file_download and file_upload through a real MCP client."""

from __future__ import annotations

import base64
import json

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from computer.docker import CommandResult
from computer.files import LIST_SCRIPT, READ_SCRIPT, WRITE_SCRIPT, Files
from computer.machine import HOME
from computer.tools.computer_page import UPLOAD_NEEDS_CONTROL
from tests.conftest import NAME, FakeDocker, server_with

FILE_CALL = ["exec", "-i", NAME, "python3", "-c"]
MIB = 1024 * 1024
HELLO = base64.b64encode(b"hi there").decode()
ENTRIES = [
    {"path": "notes/a", "kind": "dir", "size": 4096},
    {"path": "notes/hello.txt", "kind": "file", "size": 8},
]
FILE_TOOLS = ("file_read", "file_download", "file_upload")


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


def arguments_for(tool: str, path: str) -> dict[str, object]:
    return {"path": path, "content_base64": HELLO} if tool == "file_upload" else {"path": path}


async def call(docker: FakeDocker, tool: str, args: dict[str, object]) -> CallToolResult:
    async with Client(server_with(docker)) as client:
        return await client.call_tool(tool, args)


def file_calls(docker: FakeDocker) -> list[tuple[list[str], str]]:
    calls = zip(docker.calls, docker.stdins, strict=True)
    return [(call[5:], stdin) for call, stdin in calls if call[:5] == FILE_CALL]


async def test_listing_returns_the_folder_and_its_entries() -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, json.dumps(ENTRIES) + "\n", "")

    result = await call(docker, "file_list", {"path": "/notes/"})

    assert result.structured_content == {"path": "notes", "entries": ENTRIES}
    assert file_calls(docker) == [([LIST_SCRIPT, HOME, "/home/rakazo/notes", "notes"], "")]


async def test_an_empty_path_lists_the_home_folder() -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, "[]\n", "")

    result = await call(docker, "file_list", {"path": ""})

    assert result.structured_content == {"path": "", "entries": []}
    assert file_calls(docker) == [([LIST_SCRIPT, HOME, "/home/rakazo", ""], "")]


@pytest.mark.parametrize("path", ["null", "[1]", "{}"])
async def test_a_path_that_reads_as_json_is_still_a_path(path: str) -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, "[]\n", "")

    result = await call(docker, "file_list", {"path": path})

    assert result.structured_content == {"path": path, "entries": []}
    assert file_calls(docker) == [([LIST_SCRIPT, HOME, f"/home/rakazo/{path}", path], "")]


async def test_reading_returns_the_text_read_up_to_two_mebibytes() -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, base64.b64encode("héllo\n".encode()).decode(), "")

    result = await call(docker, "file_read", {"path": "notes/hello.txt"})

    assert result.structured_content == {"path": "notes/hello.txt", "content": "héllo\n"}
    assert file_calls(docker) == [
        ([READ_SCRIPT, HOME, "/home/rakazo/notes/hello.txt", str(2 * MIB)], "")
    ]


async def test_a_file_that_is_not_utf8_text_is_refused_for_preview() -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, base64.b64encode(b"\xff\xd8\xff\xe0").decode(), "")

    result = await call(docker, "file_read", {"path": "photo.jpg"})

    assert result.is_error
    assert "~/photo.jpg is not UTF-8 text" in text_of(result)


async def test_downloading_returns_the_bytes_as_base64_read_up_to_ten_mebibytes() -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, HELLO, "")

    result = await call(docker, "file_download", {"path": "notes/hello.txt"})

    assert result.structured_content == {"path": "notes/hello.txt", "content_base64": HELLO}
    assert file_calls(docker) == [
        ([READ_SCRIPT, HOME, "/home/rakazo/notes/hello.txt", str(10 * MIB)], "")
    ]


@pytest.mark.parametrize(("tool", "limit"), [("file_read", "2 MiB"), ("file_download", "10 MiB")])
async def test_a_file_past_the_limit_is_refused(tool: str, limit: str) -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(42, "", "")

    result = await call(docker, tool, {"path": "big.iso"})

    assert result.is_error
    assert f"~/big.iso is larger than {limit}" in text_of(result)


async def test_a_missing_file_reaches_the_computer_page_in_the_computers_words() -> None:
    docker = FakeDocker(status="running")
    said = "[Errno 2] No such file or directory: '/home/rakazo/nope'"
    docker.python_result = CommandResult(1, "", said + "\n")

    result = await call(docker, "file_read", {"path": "nope"})

    assert result.is_error
    assert text_of(result).endswith(f"Reading ~/nope failed: {said}")
    assert "not available" not in text_of(result)


@pytest.mark.parametrize(
    ("tool", "answer"),
    [("file_list", "not json"), ("file_list", '[{"path": 1}]'), ("file_download", "!!")],
)
async def test_an_answer_this_server_cannot_read_is_an_error(tool: str, answer: str) -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, answer, "")

    result = await call(docker, tool, {"path": "notes"})

    assert result.is_error
    assert "cannot read" in text_of(result)


async def test_an_upload_without_control_is_refused_before_any_docker_call() -> None:
    docker = FakeDocker(status="exited")
    async with Client(server_with(docker)) as client:
        at_startup = list(docker.calls)
        result = await client.call_tool("file_upload", arguments_for("file_upload", "a.txt"))

    assert result.is_error
    assert text_of(result).endswith(UPLOAD_NEEDS_CONTROL)
    assert docker.calls == at_startup


async def test_an_upload_with_control_sends_the_bytes_on_stdin() -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        result = await client.call_tool("file_upload", arguments_for("file_upload", "notes/a.txt"))

    assert result.structured_content == {"path": "notes/a.txt", "size": 8}
    assert file_calls(docker) == [([WRITE_SCRIPT, HOME, "/home/rakazo/notes/a.txt"], HELLO)]


@pytest.mark.parametrize("path", ["../etc/passwd", "notes/../../etc", "./x", "..\\etc", "a\x00b"])
@pytest.mark.parametrize("tool", ["file_list", *FILE_TOOLS])
async def test_a_path_that_could_leave_home_is_refused_before_any_docker_call(
    tool: str, path: str
) -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        before = list(docker.calls)
        result = await client.call_tool(tool, arguments_for(tool, path))

    assert result.is_error
    assert docker.calls == before


async def test_a_path_that_skipped_the_parser_is_refused_before_any_docker_call() -> None:
    docker = FakeDocker(status="running")
    docker.python_result = CommandResult(0, "[]\n", "")

    with pytest.raises(AttributeError, match="absolute"):
        await Files(docker=docker, container=NAME).listing("notes")

    assert docker.calls == []


@pytest.mark.parametrize("path", ["", "/"])
@pytest.mark.parametrize("tool", FILE_TOOLS)
async def test_a_file_tool_needs_a_file_not_the_home_folder(tool: str, path: str) -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        before = list(docker.calls)
        result = await client.call_tool(tool, arguments_for(tool, path))

    assert result.is_error
    assert docker.calls == before


@pytest.mark.parametrize("content", [base64.b64encode(bytes(10 * MIB + 1)).decode(), "!!"])
async def test_an_upload_too_large_or_not_base64_is_refused_before_any_docker_call(
    content: str,
) -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        before = list(docker.calls)
        result = await client.call_tool("file_upload", {"path": "a", "content_base64": content})

    assert result.is_error
    assert docker.calls == before
