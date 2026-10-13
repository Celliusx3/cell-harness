"""The real computer: this server over stdio, driving Rakazo's image in Docker."""

from __future__ import annotations

import asyncio
import base64
import os
import struct
import subprocess
import sys
from collections.abc import Iterator
from urllib.parse import parse_qs, urlsplit

import pytest
import websockets
from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, ImageContent, TextContent
from websockets.exceptions import InvalidHandshake

pytestmark = pytest.mark.skipif(os.environ.get("COMPUTER_LIVE") != "1", reason="COMPUTER_LIVE=1")

NAME = "cell-harness-computer-test"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
VNC_GREETING = b"RFB 003.008\n"
RELAY = "io.cell-harness/relay"


def text_of(result: CallToolResult) -> str:
    return "\n".join(block.text for block in result.content if isinstance(block, TextContent))


@pytest.fixture
def params() -> Iterator[StdioServerParameters]:
    yield StdioServerParameters(
        command=sys.executable,
        args=["-m", "computer.server"],
        env={**os.environ, "COMPUTER_NAME": NAME},
    )
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True, check=False)
    subprocess.run(["docker", "volume", "rm", f"{NAME}-home"], capture_output=True, check=False)


async def test_a_bot_opens_a_page_and_reads_it(params: StdioServerParameters) -> None:
    async with Client(params) as client:
        opened = await client.call_tool("browser_navigate", {"url": "https://example.com"})
        page = await client.call_tool("browser_read_page", {})

    assert not opened.is_error, text_of(opened)
    assert not page.is_error, text_of(page)
    assert "Example Domain" in text_of(page)


async def test_the_person_sees_the_screen(params: StdioServerParameters) -> None:
    async with Client(params) as client:
        result = await client.call_tool("screenshot", {})

    assert not result.is_error, text_of(result)
    (block,) = result.content
    assert isinstance(block, ImageContent)
    assert base64.b64decode(block.data).startswith(PNG_SIGNATURE)


def relay_url(result: CallToolResult) -> str:
    assert result.meta is not None, text_of(result)
    return result.meta[RELAY]["url"]


def socket_url(page_url: str) -> str:
    page = urlsplit(page_url)
    return f"ws://{page.netloc}/{parse_qs(page.query)['path'][0]}"


async def greeting(url: str) -> bytes:
    async with websockets.connect(url, subprotocols=["binary"]) as screen:
        return await asyncio.wait_for(screen.recv(), 10)


async def test_the_person_watches_the_screen_live(params: StdioServerParameters) -> None:
    async with Client(params) as client:
        watching = await client.call_tool("screen_session", {"mode": "view"})

        assert not watching.is_error, text_of(watching)
        assert await greeting(socket_url(relay_url(watching))) == VNC_GREETING


async def test_the_person_takes_control_and_the_bot_waits_until_released(
    params: StdioServerParameters,
) -> None:
    async with Client(params) as client:
        held = await client.call_tool("screen_session", {"mode": "control"})
        control = socket_url(relay_url(held))
        greeted = await greeting(control)
        refused = await client.call_tool("browser_read_page", {})
        await client.call_tool("release_control", {})
        with pytest.raises(InvalidHandshake):
            await greeting(control)
        read = await client.call_tool("browser_read_page", {})

    assert greeted == VNC_GREETING
    assert refused.is_error and "taken control" in text_of(refused)
    assert not read.is_error, text_of(read)


def frame(kind: int, payload: bytes) -> bytes:
    return bytes([kind]) + struct.pack(">I", len(payload)) + payload


def terminal_socket_url(result: CallToolResult) -> str:
    return relay_url(result).replace("http://", "ws://", 1)


async def test_the_person_types_in_a_shell_on_the_computer(params: StdioServerParameters) -> None:
    async with Client(params) as client:
        refused = await client.call_tool("terminal_session", {})
        await client.call_tool("screen_session", {"mode": "control"})
        shell = terminal_socket_url(await client.call_tool("terminal_session", {}))
        seen = b""
        async with websockets.connect(shell, subprotocols=["binary"]) as terminal:
            await terminal.send(frame(1, struct.pack(">HH", 80, 24)))
            await terminal.send(frame(0, b"echo cell-$((40+2))\n"))
            while b"cell-42" not in seen:
                seen += await asyncio.wait_for(terminal.recv(), 10)
        await client.call_tool("release_control", {})
        with pytest.raises(InvalidHandshake):
            await greeting(shell)

    assert refused.is_error and "Take control" in text_of(refused)
    assert b"cell-42" in seen


async def test_the_person_uploads_lists_and_downloads_a_file(
    params: StdioServerParameters,
) -> None:
    content = base64.b64encode(b"hi there").decode()
    upload = {"path": "notes/hello.txt", "content_base64": content}
    async with Client(params) as client:
        await client.call_tool("screen_session", {"mode": "view"})
        refused = await client.call_tool("file_upload", upload)
        await client.call_tool("screen_session", {"mode": "control"})
        sent = await client.call_tool("file_upload", upload)
        listed = await client.call_tool("file_list", {"path": "notes"})
        fetched = await client.call_tool("file_download", {"path": "notes/hello.txt"})
        escaped = await client.call_tool("file_read", {"path": "../etc/passwd"})
        await client.call_tool("release_control", {})

    assert refused.is_error and "Take control" in text_of(refused)
    assert not sent.is_error, text_of(sent)
    assert fetched.structured_content is not None, text_of(fetched)
    assert base64.b64decode(fetched.structured_content["content_base64"]) == b"hi there"
    assert listed.structured_content is not None, text_of(listed)
    assert [entry["path"] for entry in listed.structured_content["entries"]] == ["notes/hello.txt"]
    assert escaped.is_error
