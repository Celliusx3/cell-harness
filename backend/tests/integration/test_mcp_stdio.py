"""The real SDK, a real subprocess."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp.server.apps import APP_MIME_TYPE

from harness.config.sections import McpServer
from harness.mcp import connection as connection_module
from harness.mcp.store import McpServerStore
from harness.tools.definition import Failure, Ok, ToolUi
from harness.tools.registry import ToolRegistry
from tests.unit.helpers import context_for

STUB = Path(__file__).resolve().parent.parent / "mcp_stub.py"
TIMEOUT = 30.0


def stub(**env: str) -> dict[str, McpServer]:
    return {"stub": McpServer(command=sys.executable, args=("-u", str(STUB)), env=env)}


@pytest.fixture
async def live():
    """Start a store and wait for it to connect; close it however the test ends."""
    made: list[McpServerStore] = []

    async def start(servers: dict[str, McpServer]):
        store = McpServerStore(servers)
        registry = ToolRegistry()
        registry.add_provider(store.tools)
        made.append(store)
        await store.start()
        for _ in range(int(TIMEOUT * 10)):
            if store.statuses()[0].status != "connecting":
                break
            await asyncio.sleep(0.1)
        assert store.statuses()[0].status == "connected", store.statuses()[0].error
        return store, registry

    yield start
    for store in made:
        await store.aclose()


async def test_a_real_server_contributes_callable_tools(live) -> None:
    _, registry = await live(stub())

    assert "stub__echo" in [t.name for t in registry.all()]

    echo = registry.get("stub__echo")
    assert echo is not None
    outcome = await echo.invoke('{"value": "hello"}', context=context_for())

    assert isinstance(outcome, Ok)
    assert "echo: hello" in outcome.text


async def test_an_app_bound_tool_and_its_html_come_through_the_real_wire(live) -> None:
    store, registry = await live(stub())

    show = registry.get("stub__show_pid")
    assert show is not None
    outcome = await show.invoke("{}", context=context_for())

    assert isinstance(outcome, Ok)
    assert outcome.ui == ToolUi(server="stub", resource_uri="ui://stub/app.html", data=outcome.data)
    assert outcome.data["apps"] is True

    resource = await store.read_resource("stub", "ui://stub/app.html")
    assert resource.contents[0].mime_type == APP_MIME_TYPE
    assert "stub app" in resource.contents[0].text


async def test_a_tool_that_raises_comes_back_as_a_failure(live) -> None:
    _, registry = await live(stub())

    boom = registry.get("stub__boom")
    assert boom is not None

    assert isinstance(await boom.invoke("{}", context=context_for()), Failure)


async def test_closing_reaps_the_subprocess(live) -> None:
    store, registry = await live(stub())

    whoami = registry.get("stub__whoami")
    assert whoami is not None
    outcome = await whoami.invoke("{}", context=context_for())
    assert isinstance(outcome, Ok)
    pid = int(outcome.text.strip())

    await store.aclose()

    assert registry.all() == []
    for _ in range(100):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"pid {pid} survived the close")


async def test_a_server_that_stops_answering_fails_within_the_timeout(live, monkeypatch) -> None:
    monkeypatch.setattr(connection_module, "COMMAND_TIMEOUT_SECONDS", 2.0)
    store, registry = await live(stub(STUB_MODE="deaf"))

    echo = registry.get("stub__echo")
    assert echo is not None
    outcome = await asyncio.wait_for(
        echo.invoke('{"value": "anyone there"}', context=context_for()), TIMEOUT
    )

    assert isinstance(outcome, Failure)
    assert "did not answer" in outcome.message
    assert store.statuses()[0].status == "connected"
