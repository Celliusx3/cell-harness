"""terminal_session: a shell on the computer, only while the person holds control."""

from __future__ import annotations

import asyncio
from importlib import resources
from urllib.parse import parse_qs, urlsplit

from mcp import Client
from mcp.types import CallToolResult, TextContent

from computer.tools.computer_page import TERMINAL_NEEDS_CONTROL
from tests.conftest import GATEWAY_HOST_PORT, NAME, Dial, FakeDocker, server_with, settle

RELAY = "io.cell-harness/relay"
HOLD_SECONDS = 15 * 60
TERMINAL_CALL = ["exec", "-i", NAME, "bash", "-c"]
PROGRAM = resources.files("computer").joinpath("vendor/rakazo_terminal.py").read_text("utf-8")
TERMINAL_STOPPED = "pkill -f '^([^ ]*/)?python[0-9.]* /tmp/rakazo/rakazo-terminal.py"


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


def terminal_token(result: CallToolResult) -> str:
    assert not result.is_error, text_of(result)
    assert result.meta is not None
    return parse_qs(urlsplit(result.meta[RELAY]["url"]).query)["token"][0]


def opened_shells(docker: FakeDocker) -> list[tuple[str, str]]:
    calls = zip(docker.calls, docker.stdins, strict=True)
    return [(call[-1], stdin) for call, stdin in calls if call[:5] == TERMINAL_CALL]


async def test_without_control_the_shell_is_refused_before_any_docker_call() -> None:
    docker = FakeDocker(status="exited")
    async with Client(server_with(docker)) as client:
        at_startup = list(docker.calls)
        result = await client.call_tool("terminal_session", {})

    assert result.is_error
    assert text_of(result).endswith(TERMINAL_NEEDS_CONTROL)
    assert docker.calls == at_startup


async def test_with_control_the_program_goes_on_stdin_and_the_link_is_the_gateway_socket() -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        opened = await client.call_tool("terminal_session", {})

    token = terminal_token(opened)
    ((script, stdin),) = opened_shells(docker)
    assert opened.meta is not None
    url = urlsplit(opened.meta[RELAY]["url"])
    assert (url.scheme, url.netloc, url.path) == (
        "http",
        f"127.0.0.1:{GATEWAY_HOST_PORT}",
        "/websockify",
    )
    assert stdin == PROGRAM
    assert "pty.fork()" in PROGRAM and "pty.fork()" not in script
    assert f"printf '%s: unix_socket:%s\\n' {token} /tmp/rakazo/sockets/terminal-1-" in script
    assert "--token-source=/tmp/rakazo/desktop-targets 0.0.0.0:6080" in script


async def test_every_shell_gets_a_token_of_its_own() -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        first = await client.call_tool("terminal_session", {})
        second = await client.call_tool("terminal_session", {})

    assert terminal_token(first) != terminal_token(second)


async def test_releasing_control_stops_the_shell() -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        opened = await client.call_tool("terminal_session", {})
        await client.call_tool("release_control", {})

    assert terminal_token(opened)
    assert TERMINAL_STOPPED in docker.scripts()[-1]
    assert ": >/tmp/rakazo/terminal-target-next-1" in docker.scripts()[-1]


async def test_a_hold_that_runs_out_stops_the_shell_too() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        opened = await client.call_tool("terminal_session", {})
        await dial.turn(HOLD_SECONDS)

        assert terminal_token(opened)
        assert TERMINAL_STOPPED in docker.scripts()[-1]


async def test_a_hold_that_runs_out_while_the_shell_is_opening_refuses_it() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("screen_session", {"mode": "control"})
        docker.gates["inspect"] = asyncio.Event()
        opening = asyncio.create_task(client.call_tool("terminal_session", {}))
        await settle()
        await dial.turn(HOLD_SECONDS)
        docker.gates["inspect"].set()
        result = await opening

    assert result.is_error
    assert text_of(result).endswith(TERMINAL_NEEDS_CONTROL)
    assert opened_shells(docker) == []
