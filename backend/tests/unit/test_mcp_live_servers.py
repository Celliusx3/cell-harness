"""Adding, changing and removing a saved server starts, restarts or stops only that server."""

from __future__ import annotations

import asyncio

import pytest

from harness.config.sections import McpServer
from harness.mcp import McpServerBuiltIn, McpServerNotFound, McpServerTaken, McpService
from tests.unit.mcp_fakes import FakeFactory, servers, tool

EXA = McpServer(command="npx", args=("-y", "exa-mcp-server"))


async def settled(store: McpService) -> None:
    for _ in range(200):
        if all(s.status != "connecting" for s in store.statuses()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("never left `connecting`")


@pytest.fixture
async def store():
    factory = FakeFactory()
    factory.client.tools = [tool("search")]
    started = McpService(servers("fs"), saved={}, client_factory=factory)
    await started.start()
    await settled(started)
    yield started, factory
    await started.aclose()


def status_of(store: McpService, server_id: str) -> str:
    return next(s.status for s in store.statuses() if s.id == server_id)


async def test_an_added_server_starts_and_its_tools_are_offered(store) -> None:
    mcp, factory = store

    await mcp.add("exa", EXA)
    await settled(mcp)

    assert status_of(mcp, "exa") == "connected"
    assert "exa__search" in {t.name for t in mcp.tools()}
    assert factory.started[-1].command == "npx"
    assert not mcp.is_built_in("exa")
    assert mcp.is_built_in("fs")


async def test_adding_starts_only_that_server(store) -> None:
    mcp, factory = store
    opened = factory.opens

    await mcp.add("exa", EXA)
    await settled(mcp)

    assert factory.opens == opened + 1
    assert status_of(mcp, "fs") == "connected"


async def test_a_change_restarts_the_server_with_its_new_command(store) -> None:
    mcp, factory = store
    await mcp.add("exa", EXA)
    await settled(mcp)

    await mcp.change("exa", EXA.model_copy(update={"command": "uvx"}))
    await settled(mcp)

    assert factory.started[-1].command == "uvx"
    assert mcp.server("exa").command == "uvx"
    assert status_of(mcp, "exa") == "connected"


async def test_a_removed_server_stops_and_its_tools_go(store) -> None:
    mcp, _ = store
    await mcp.add("exa", EXA)
    await settled(mcp)

    await mcp.remove("exa")

    assert "exa" not in {s.id for s in mcp.statuses()}
    assert not any(t.name.startswith("exa__") for t in mcp.tools())
    assert "fs__search" in {t.name for t in mcp.tools()}
    with pytest.raises(KeyError):
        mcp.server("exa")


async def test_an_id_already_served_is_refused(store) -> None:
    mcp, factory = store
    await mcp.add("exa", EXA)
    opened = factory.opens

    with pytest.raises(McpServerTaken):
        await mcp.add("fs", EXA)
    with pytest.raises(McpServerTaken):
        await mcp.add("exa", EXA)

    assert factory.opens == opened


async def test_a_built_in_server_cannot_be_changed_or_removed(store) -> None:
    mcp, _ = store

    with pytest.raises(McpServerBuiltIn):
        await mcp.change("fs", EXA)
    with pytest.raises(McpServerBuiltIn):
        await mcp.remove("fs")

    assert status_of(mcp, "fs") == "connected"


async def test_an_unknown_server_cannot_be_changed_or_removed(store) -> None:
    mcp, _ = store

    with pytest.raises(McpServerNotFound):
        await mcp.change("nowhere", EXA)
    with pytest.raises(McpServerNotFound):
        await mcp.remove("nowhere")


async def test_saved_servers_start_with_the_built_in_ones() -> None:
    factory = FakeFactory()
    mcp = McpService(servers("fs"), saved={"exa": EXA}, client_factory=factory)

    await mcp.start()
    await settled(mcp)

    assert [(s.id, s.status) for s in mcp.statuses()] == [
        ("fs", "connected"),
        ("exa", "connected"),
    ]
    await mcp.aclose()


async def test_a_saved_server_with_a_built_in_id_stops_startup() -> None:
    with pytest.raises(McpServerTaken, match="fs"):
        McpService(servers("fs"), saved={"fs": EXA}, client_factory=FakeFactory())


async def test_a_saved_server_that_needs_a_key_waits(store) -> None:
    mcp, _ = store

    await mcp.add("exa", EXA.model_copy(update={"needs": ("EXA_API_KEY",)}))

    assert status_of(mcp, "exa") == "waiting"
    assert mcp.server("exa").needs == ("EXA_API_KEY",)
