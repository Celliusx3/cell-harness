"""A skill declares PhotoCraft; a command in the real computer reaches it and opens a chat file."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.types import CallToolResult, TextContent

from tests.fake_host_service import write_skill

pytestmark = [
    pytest.mark.skipif(os.environ.get("COMPUTER_LIVE") != "1", reason="COMPUTER_LIVE=1"),
    pytest.mark.skipif(shutil.which("photocraft-cli") is None, reason="needs PhotoCraft"),
]

NAME = "cell-harness-computer-shell-test"
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
DECLARES_PHOTOCRAFT = """name: photocraft
description: Opens and saves images with PhotoCraft on the Mac.
metadata:
  host-service: photocraft-cli serve --port {port} --control-token-file {token_file} --automation-read-root {files} --automation-write-root {files}
  host-service-env: PHOTOCRAFT"""  # noqa: E501
ASK_PHOTOCRAFT = """
import json, os, socket, sys
host, port = os.environ["PHOTOCRAFT_ADDR"].rsplit(":", 1)
stream = socket.create_connection((host, int(port)), timeout=20).makefile("rwb")
def ask(number, method, params):
    stream.write((json.dumps({"id": number, "method": method, "params": params}) + "\\n").encode())
    stream.flush()
    return json.loads(stream.readline())
print(json.dumps({
    "signed_in": ask(1, "auth", {"token": os.environ["PHOTOCRAFT_TOKEN"]}),
    "opened": ask(2, "doc.open", {"path": sys.argv[1]}),
}))
"""


def text_of(result: CallToolResult) -> str:
    return "\n".join(block.text for block in result.content if isinstance(block, TextContent))


@pytest.fixture
def files(tmp_path: Path) -> Path:
    (tmp_path / "files").mkdir()
    write_skill(tmp_path / "skills", "photocraft", DECLARES_PHOTOCRAFT)
    return (tmp_path / "files").resolve()


@pytest.fixture
def params(files: Path) -> Iterator[StdioServerParameters]:
    yield StdioServerParameters(
        command=sys.executable,
        args=["-m", "computer.server"],
        env={
            **os.environ,
            "COMPUTER_NAME": NAME,
            "COMPUTER_FILES_DIR": str(files),
            "COMPUTER_SKILLS_DIRS": str(files.parent / "skills"),
        },
    )
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True, check=False)
    subprocess.run(["docker", "volume", "rm", f"{NAME}-home"], capture_output=True, check=False)


async def test_a_command_signs_in_to_the_declared_photocraft_and_opens_a_chat_file(
    params: StdioServerParameters, files: Path
) -> None:
    page = files / "chat" / "token" / "page.png"
    page.parent.mkdir(parents=True)
    page.write_bytes(ONE_PIXEL_PNG)
    call = {"command": f"python3 - {page}", "stdin": ASK_PHOTOCRAFT}
    async with Client(params) as client:
        result = await client.call_tool("shell", call)

    assert not result.is_error, text_of(result)
    done = result.structured_content
    assert done is not None and done["exit_code"] == 0, done
    asked = json.loads(done["output"].strip().splitlines()[-1])
    assert asked["signed_in"]["result"] == {"authenticated": True}
    assert asked["opened"]["ok"] is True
    assert asked["opened"]["result"]["width"] == 1


async def test_the_declared_photocraft_is_gone_once_the_computer_server_stops(
    params: StdioServerParameters,
) -> None:
    async with Client(params) as client:
        await client.call_tool("shell", {"command": "true"})

    left = subprocess.run(["pgrep", "-f", "photocraft-cli serve"], capture_output=True, text=True)
    assert (
        str(params.env["COMPUTER_FILES_DIR"])
        not in subprocess.run(
            ["ps", "-o", "command=", "-p", *left.stdout.split()]
            if left.stdout.split()
            else ["true"],
            capture_output=True,
            text=True,
        ).stdout
    )
