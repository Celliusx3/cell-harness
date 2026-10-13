"""screen_session and release_control: the live screen, and the hold that keeps the bots off."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlsplit

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

from computer.tools.descriptions import HELD_BY_PERSON
from tests.conftest import (
    GATEWAY_HOST_PORT,
    IDLE_SECONDS,
    NAME,
    SNAPSHOT,
    Dial,
    FakeDocker,
    server_with,
)

RELAY = "io.cell-harness/relay"
HOLD_SECONDS = 15 * 60
CLICK = {"kind": "click", "ref": "e1"}
BROWSER_CALLS = [
    ("browser_navigate", {"url": "https://example.com"}),
    ("browser_read_page", {}),
    ("browser_act", {"actions": [CLICK]}),
]


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


def url_of(result: CallToolResult) -> str:
    assert not result.is_error, text_of(result)
    assert result.meta is not None
    return result.meta[RELAY]["url"]


def token_of(result: CallToolResult) -> str:
    (path,) = parse_qs(urlsplit(url_of(result)).query)["path"]
    return parse_qs(urlsplit(path).query)["token"][0]


def stop_count(docker: FakeDocker) -> int:
    return docker.calls.count(["stop", NAME])


async def test_view_runs_the_view_script_and_returns_the_loopback_url_of_the_published_port() -> (
    None
):
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        result = await client.call_tool("screen_session", {"mode": "view"})

    url = urlsplit(url_of(result))
    (script,) = docker.scripts()
    assert "-viewonly" in script
    assert ["port", NAME, "6080"] in docker.calls
    assert (url.scheme, url.netloc, url.path) == (
        "http",
        f"127.0.0.1:{GATEWAY_HOST_PORT}",
        "/embed.html",
    )
    assert parse_qs(url.query)["view_only"] == ["1"]
    assert token_of(result) in script
    assert result.structured_content == {"mode": "view", "held_until": None}


async def test_a_second_view_reuses_the_same_view_token() -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        first = await client.call_tool("screen_session", {"mode": "view"})
        second = await client.call_tool("screen_session", {"mode": "view"})

    assert token_of(first) == token_of(second)


async def test_control_runs_the_control_script_and_holds_for_fifteen_minutes() -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        view = await client.call_tool("screen_session", {"mode": "view"})
        held = await client.call_tool("screen_session", {"mode": "control"})

    (_, script) = docker.scripts()
    assert "x11vnc" in script
    assert "-viewonly" not in script
    assert parse_qs(urlsplit(url_of(held)).query)["view_only"] == ["0"]
    assert token_of(held) in script
    assert token_of(held) != token_of(view)
    assert held.structured_content == {"mode": "control", "held_until": "2026-10-13T09:15:00Z"}


@pytest.mark.parametrize(("tool", "args"), BROWSER_CALLS)
async def test_while_held_a_browser_tool_is_refused_and_sends_nothing(
    tool: str, args: dict[str, object]
) -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        before = list(docker.calls)
        result = await client.call_tool(tool, args)

    assert result.is_error
    assert text_of(result).endswith(f": {HELD_BY_PERSON}")
    assert docker.calls == before


async def test_release_runs_the_release_script_and_the_browser_works_again() -> None:
    docker = FakeDocker(status="running", page_replies=[SNAPSHOT])
    async with Client(server_with(docker)) as client:
        held = await client.call_tool("screen_session", {"mode": "control"})
        released = await client.call_tool("release_control", {})
        read = await client.call_tool("browser_read_page", {})

    (_, script) = docker.scripts()
    assert "control-target-next-1" in script
    assert token_of(held) in script
    assert released.structured_content == {"mode": "view", "held_until": None}
    assert not read.is_error, text_of(read)


async def test_releasing_when_nothing_is_held_makes_no_docker_call_and_starts_nothing() -> None:
    docker = FakeDocker(status="exited")
    async with Client(server_with(docker)) as client:
        at_startup = list(docker.calls)
        released = await client.call_tool("release_control", {})

    assert released.structured_content == {"mode": "view", "held_until": None}
    assert docker.calls == at_startup
    assert docker.status == "exited"


async def test_the_hold_ends_on_its_own_when_held_until_passes() -> None:
    docker, dial = FakeDocker(status="running", page_replies=[SNAPSHOT]), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        await dial.turn(HOLD_SECONDS - 1)
        assert len(docker.scripts()) == 1

        await dial.turn(1)
        read = await client.call_tool("browser_read_page", {})

    (_, script) = docker.scripts()
    assert "control-target-next-1" in script
    assert not read.is_error, text_of(read)


async def test_taking_control_again_keeps_the_token_and_moves_held_until() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)) as client:
        first = await client.call_tool("screen_session", {"mode": "control"})
        await dial.turn(300)
        again = await client.call_tool("screen_session", {"mode": "control"})
        await dial.turn(HOLD_SECONDS - 300)
        assert len(docker.scripts()) == 2

        await dial.turn(300)

        assert len(docker.scripts()) == 3

    assert token_of(again) == token_of(first)
    assert again.structured_content == {"mode": "control", "held_until": "2026-10-13T09:20:00Z"}


async def test_while_held_the_idle_stop_never_fires_and_comes_back_after_release() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        await dial.turn(IDLE_SECONDS)
        await dial.turn(HOLD_SECONDS - IDLE_SECONDS - 1)
        assert stop_count(docker) == 0

        await dial.turn(1)
        await dial.turn(IDLE_SECONDS - 1)
        assert stop_count(docker) == 0

        await dial.turn(1)

        assert stop_count(docker) == 1


async def test_screen_session_starts_a_stopped_computer_first() -> None:
    docker = FakeDocker(status="exited")
    async with Client(server_with(docker)) as client:
        result = await client.call_tool("screen_session", {"mode": "view"})

    assert not result.is_error, text_of(result)
    assert docker.verbs().index("start") < docker.verbs().index("port")


async def test_a_mode_that_is_neither_view_nor_control_is_refused_before_any_docker_call() -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        before = list(docker.calls)
        result = await client.call_tool("screen_session", {"mode": "drive"})

    assert result.is_error
    assert docker.calls == before


async def test_a_script_docker_refuses_reaches_the_computer_page_as_an_error() -> None:
    docker = FakeDocker(status="running")
    docker.refused_verbs.add("exec")
    async with Client(server_with(docker)) as client:
        result = await client.call_tool("screen_session", {"mode": "control"})
        read = await client.call_tool("browser_read_page", {})

    assert result.is_error
    assert "The computer is not available: taking control of the screen failed" in text_of(result)
    assert HELD_BY_PERSON not in text_of(read)


async def test_a_hold_that_runs_out_ends_even_when_its_release_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        docker.refused_verbs.add("exec")
        with caplog.at_level(logging.ERROR, logger="computer"):
            await dial.turn(HOLD_SECONDS)
        read = await client.call_tool("browser_read_page", {})

    assert "may still be open" in caplog.text
    assert HELD_BY_PERSON not in text_of(read)
