"""The screenshot tool: one PNG of the whole desktop, from one command in the PC."""

from __future__ import annotations

import base64

import pytest
from mcp import Client
from mcp.types import CallToolResult, ImageContent, TextContent

from computer.engines.docker import DockerEngine
from computer.models.command import CommandResult
from computer.services.desktop import Desktop, DesktopError
from tests.conftest import IDLE_SECONDS, NAME, PNG, Dial, FakeDocker, server_with

STOP = ["stop", NAME]
SCREENSHOT_CALL = [
    "exec", "-e", "DISPLAY=:1", NAME, "bash", "-o", "pipefail", "-c", "scrot - | base64 -w 0"
]  # fmt: skip


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


async def screenshot_result(docker: FakeDocker) -> CallToolResult:
    async with Client(server_with(docker)) as client:
        return await client.call_tool("screenshot", {})


async def test_screenshot_returns_one_png_image_of_the_commands_stdout_and_nothing_else() -> None:
    result = await screenshot_result(FakeDocker(status="running"))

    assert not result.is_error, text_of(result)
    (block,) = result.content
    assert isinstance(block, ImageContent)
    assert block.mime_type == "image/png"
    assert base64.b64decode(block.data) == PNG
    assert result.structured_content is None


async def test_the_screenshot_is_scrot_piped_to_base64_on_the_pcs_display() -> None:
    docker = FakeDocker(status="running")

    await screenshot_result(docker)

    assert SCREENSHOT_CALL in docker.calls


async def test_the_desktop_reads_the_screen_as_the_commands_stdout() -> None:
    desktop = Desktop(engine=DockerEngine(docker=FakeDocker(status="running")), container=NAME)

    shot = await desktop.screenshot()

    assert base64.b64decode(shot.image) == PNG
    assert shot.mime_type == "image/png"


@pytest.mark.parametrize(
    ("stdout", "said"),
    [
        (base64.b64encode(b"GIF89a").decode(), "not a PNG"),
        ("not base64!", "not a PNG"),
        ("", "not a PNG"),
    ],
)
async def test_output_that_is_not_a_png_is_an_error_never_a_picture(stdout: str, said: str) -> None:
    docker = FakeDocker(status="running")
    docker.screenshot = CommandResult(0, stdout, "")
    desktop = Desktop(engine=DockerEngine(docker=docker), container=NAME)

    with pytest.raises(DesktopError, match=said):
        await desktop.screenshot()


async def test_a_failing_command_is_an_error_saying_what_failed() -> None:
    docker = FakeDocker(status="running")
    docker.screenshot = CommandResult(
        1, "", "scrot: Can't open X display. It *is* running, yeah? [:1]"
    )

    result = await screenshot_result(docker)

    assert result.is_error
    assert "the screenshot failed: scrot: Can't open X display" in text_of(result)
    assert not any(isinstance(block, ImageContent) for block in result.content)


async def test_screenshot_starts_a_stopped_computer_first() -> None:
    docker = FakeDocker(status="exited")

    result = await screenshot_result(docker)

    assert not result.is_error, text_of(result)
    assert docker.verbs().index("start") < docker.calls.index(SCREENSHOT_CALL)


async def test_a_screenshot_call_postpones_the_idle_stop() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("screenshot", {})
        await dial.turn(IDLE_SECONDS - 60)
        await client.call_tool("screenshot", {})
        await dial.turn(IDLE_SECONDS - 60)
        assert STOP not in docker.calls

        await dial.turn(60)

        assert docker.calls[-1] == STOP


async def test_a_docker_failure_reaches_the_preview_as_an_error() -> None:
    docker = FakeDocker(status="running")
    docker.unreachable = True

    result = await screenshot_result(docker)

    assert result.is_error
    assert "docker is not on PATH" in text_of(result)
