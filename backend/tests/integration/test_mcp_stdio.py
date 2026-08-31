"""The real SDK, a real subprocess.

Everything else in the MCP suite runs against a fake session, which is right —
the command loop is about tasks and deadlines. This file exists to prove the
assumptions those tests are built on actually hold against `mcp`: that a failing
tool comes back as `is_error` rather than an exception, that a timed-out call
leaves the connection usable, and that closing really reaps the process.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from harness.config.settings import McpServer
from harness.mcp import store as store_module
from harness.mcp.store import McpServerStore
from harness.tools.definition import Failure, Ok
from harness.tools.registry import ToolRegistry
from tests.unit.helpers import no_progress

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

    assert "stub__echo" in [spec.name for spec in registry.specs()]

    # Through the registry, the way the agent loop reaches a tool.
    echo = registry.get("stub__echo")
    assert echo is not None
    outcome = await echo.invoke('{"value": "hello"}', progress=no_progress)

    assert isinstance(outcome, Ok)
    assert "echo: hello" in outcome.content


async def test_a_tool_that_raises_comes_back_as_a_failure(live) -> None:
    """The SDK returns `is_error=True`; it does not raise. The model can recover."""
    _, registry = await live(stub())

    boom = registry.get("stub__boom")
    assert boom is not None

    assert isinstance(await boom.invoke("{}", progress=no_progress), Failure)


async def test_closing_reaps_the_subprocess(live) -> None:
    """Proved rather than assumed: the pid really is gone."""
    store, registry = await live(stub())

    whoami = registry.get("stub__whoami")
    assert whoami is not None
    outcome = await whoami.invoke("{}", progress=no_progress)
    assert isinstance(outcome, Ok)
    pid = int(outcome.content.strip())

    await store.aclose()

    assert registry.specs() == []
    for _ in range(100):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"pid {pid} survived the close")


async def test_a_server_that_stops_answering_fails_within_the_timeout(live, monkeypatch) -> None:
    """A server that accepts connections and then goes quiet."""
    monkeypatch.setattr(store_module, "COMMAND_TIMEOUT_SECONDS", 2.0)
    store, registry = await live(stub(STUB_MODE="deaf"))

    echo = registry.get("stub__echo")
    assert echo is not None
    outcome = await asyncio.wait_for(
        echo.invoke('{"value": "anyone there"}', progress=no_progress), TIMEOUT
    )

    assert isinstance(outcome, Failure)
    assert "did not answer" in outcome.message
    # Still connected: a slow tool is not a dead server.
    assert store.statuses()[0].status == "connected"
