"""The screenshot tool: one PNG of the whole desktop, from the API endpoint, through the machine."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from mcp import Client
from mcp.types import CallToolResult, ImageContent, TextContent

from computer.desktop import DesktopError, api_token, published_port
from tests.conftest import (
    API_HOST_PORT,
    API_TOKEN,
    IDLE_SECONDS,
    NAME,
    PNG,
    SCREENSHOT_REPLY,
    Dial,
    FakeDesktopApi,
    FakeDocker,
    server_with,
)

STOP = ["stop", NAME]


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


def desktop_reply(**observation: object) -> httpx.Response:
    return httpx.Response(200, json={**SCREENSHOT_REPLY, "observation": observation})


async def screenshot_result(docker: FakeDocker, desktop_api: FakeDesktopApi) -> CallToolResult:
    async with Client(server_with(docker, desktop_api=desktop_api)) as client:
        return await client.call_tool("screenshot", {})


async def test_screenshot_returns_one_png_image_of_the_endpoints_bytes_and_nothing_else() -> None:
    result = await screenshot_result(FakeDocker(status="running"), FakeDesktopApi())

    assert not result.is_error, text_of(result)
    (block,) = result.content
    assert isinstance(block, ImageContent)
    assert block.mime_type == "image/png"
    assert base64.b64decode(block.data) == PNG
    assert result.structured_content is None


async def test_screenshot_asks_the_published_port_with_the_containers_token() -> None:
    docker, desktop_api = FakeDocker(status="running"), FakeDesktopApi()

    await screenshot_result(docker, desktop_api)

    (request,) = desktop_api.seen
    assert (request.method, str(request.url)) == (
        "POST",
        f"http://127.0.0.1:{API_HOST_PORT}/v1/desktop",
    )
    assert request.headers["Authorization"] == f"Bearer {API_TOKEN}"
    assert json.loads(request.content) == {"display": ":1", "steps": [], "observe": True}
    assert ["port", NAME, "7070"] in docker.calls


async def test_a_computer_this_server_made_is_asked_with_the_token_it_was_made_with() -> None:
    docker, desktop_api = FakeDocker(status="missing"), FakeDesktopApi()

    await screenshot_result(docker, desktop_api)

    run = next(call for call in docker.calls if call[0] == "run")
    made = next(arg for arg in run if arg.startswith("RAKAZO_COMPUTER_CONTROL_TOKEN="))
    assert desktop_api.seen[0].headers["Authorization"] == f"Bearer {made.split('=', 1)[1]}"


async def test_screenshot_starts_a_stopped_computer_first() -> None:
    docker = FakeDocker(status="exited")

    result = await screenshot_result(docker, FakeDesktopApi())

    assert not result.is_error, text_of(result)
    assert docker.verbs().index("start") < docker.verbs().index("port")


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


async def test_the_port_is_read_again_after_the_computer_starts_again() -> None:
    docker, dial, desktop_api = FakeDocker(status="running"), Dial(), FakeDesktopApi()
    async with Client(server_with(docker, dial, desktop_api)) as client:
        await client.call_tool("screenshot", {})
        await dial.turn(IDLE_SECONDS)
        await client.call_tool("screenshot", {})

    assert [request.url.port for request in desktop_api.seen] == [API_HOST_PORT, API_HOST_PORT + 1]


@pytest.mark.parametrize(
    ("reply", "said"),
    [
        (httpx.Response(401, text="<h1>Unauthorized</h1>"), "refused the screenshot: 401"),
        (httpx.Response(500, text="boom"), "refused the screenshot: 500"),
        (httpx.ConnectError("Connection refused"), "did not answer: ConnectError"),
        (httpx.ReadTimeout("timed out"), "did not answer: ReadTimeout"),
        (httpx.Response(200, text="not json"), "cannot read"),
        (httpx.Response(200, json={"completed": 0}), "cannot read"),
        (
            desktop_reply(image=SCREENSHOT_REPLY["observation"]["image"], mimeType="image/jpeg"),
            "cannot read",
        ),
        (desktop_reply(image="not base64!", mimeType="image/png"), "cannot read"),
        (
            desktop_reply(image=base64.b64encode(b"GIF89a").decode(), mimeType="image/png"),
            "cannot read",
        ),
    ],
)
async def test_a_refused_or_unreadable_reply_is_an_error_never_a_picture(
    reply: httpx.Response | httpx.HTTPError, said: str
) -> None:
    result = await screenshot_result(FakeDocker(status="running"), FakeDesktopApi(reply))

    assert result.is_error
    assert said in text_of(result)
    assert not any(isinstance(block, ImageContent) for block in result.content)


async def test_a_docker_failure_on_the_port_reaches_the_preview_as_an_error() -> None:
    docker = FakeDocker(status="running")
    docker.refused_verbs.add("port")

    result = await screenshot_result(docker, FakeDesktopApi())

    assert result.is_error
    assert "The computer is not available: docker port failed" in text_of(result)


def test_the_api_port_is_the_one_published_on_loopback() -> None:
    assert published_port(f"127.0.0.1:{API_HOST_PORT}\n", 7070) == API_HOST_PORT


@pytest.mark.parametrize("published", ["", "0.0.0.0:62477\n[::]:62477\n", "127.0.0.1:\n"])
def test_a_port_not_published_on_loopback_is_refused(published: str) -> None:
    with pytest.raises(DesktopError, match="port 6080 is not published on 127.0.0.1"):
        published_port(published, 6080)


def test_the_token_is_read_from_the_containers_environment() -> None:
    env = ["DISPLAY=:1", f"RAKAZO_COMPUTER_CONTROL_TOKEN={API_TOKEN}", "HOME=/home/rakazo"]

    assert api_token(json.dumps(env) + "\n") == API_TOKEN


@pytest.mark.parametrize(
    ("inspected", "said"),
    [
        ('["DISPLAY=:1"]', "no API token"),
        ('["RAKAZO_COMPUTER_CONTROL_TOKEN="]', "no API token"),
        ("null", "cannot read"),
        ("<no value>", "cannot read"),
    ],
)
def test_a_container_without_a_readable_token_is_refused(inspected: str, said: str) -> None:
    with pytest.raises(DesktopError, match=said):
        api_token(inspected)
