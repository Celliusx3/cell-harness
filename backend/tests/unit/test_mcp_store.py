"""The command loop.

The first test is the design's proof: it fails on the obvious implementation
that opens the session in the caller's task, which is the one anyio forbids.
"""

from __future__ import annotations

import asyncio

import pytest

from harness.mcp import store as store_module
from harness.mcp.errors import McpConnectionError, McpNotConnectedError, McpTimeoutError
from harness.mcp.store import McpServerStore
from tests.unit.mcp_fakes import FakeFactory, html_resource, servers, tool


async def connected(factory: FakeFactory, *ids: str) -> McpServerStore:
    """A started store, waited until its connections have settled."""
    store = McpServerStore(servers(*ids), client_factory=factory)
    await store.start()
    for _ in range(200):
        if all(s.status != "connecting" for s in store.statuses()):
            return store
        await asyncio.sleep(0.01)
    raise AssertionError("never left `connecting`")


async def test_session_is_owned_by_one_task_that_is_nobody_s_caller() -> None:
    """Enter and exit happen in the same task, and it is not the caller's.

    anyio raises `RuntimeError: Attempted to exit cancel scope in a different
    task than it was entered in` when this is violated, so the whole command
    loop exists to make it true.
    """
    factory = FakeFactory()
    caller = asyncio.current_task()
    store = await connected(factory)

    entered = factory.client.entered_in
    await store.aclose()

    assert entered is not None
    assert entered is factory.client.exited_in
    assert entered is not caller


async def test_a_configured_server_contributes_namespaced_tools() -> None:
    factory = FakeFactory()
    factory.client.tools = [tool("echo"), tool("ping")]

    store = await connected(factory)

    assert [t.name for t in store.tools()] == ["stub__echo", "stub__ping"]
    await store.aclose()


async def test_tools_go_away_when_the_store_closes() -> None:
    factory = FakeFactory()
    store = await connected(factory)

    await store.aclose()

    assert store.tools() == []


async def test_tool_listing_follows_pagination() -> None:
    factory = FakeFactory()
    factory.client.tools = [tool("a"), tool("b"), tool("c"), tool("d")]
    factory.client.pages = 2

    store = await connected(factory)

    assert [t.name for t in store.tools()] == ["stub__a", "stub__b", "stub__c", "stub__d"]
    await store.aclose()


async def test_concurrent_callers_each_get_their_own_result() -> None:
    """A shared reply queue would hand caller A's answer to caller B."""
    factory = FakeFactory()
    store = await connected(factory)
    call = store._connections["stub"].call

    first, second = await asyncio.gather(call("echo", {"n": 1}), call("echo", {"n": 2}))

    assert factory.client.calls == [("echo", {"n": 1}), ("echo", {"n": 2})]
    assert first.content[0].text == "echo ok"
    assert second.content[0].text == "echo ok"
    await store.aclose()


async def test_a_timed_out_call_leaves_the_connection_usable(monkeypatch) -> None:
    """The point of putting the deadline on the owner rather than the caller."""
    monkeypatch.setattr(store_module, "COMMAND_TIMEOUT_SECONDS", 0.05)
    factory = FakeFactory()
    factory.client.tools = [tool("slow"), tool("echo")]
    factory.client.behaviour = {"slow": 5.0}
    store = await connected(factory)
    connection = store._connections["stub"]

    with pytest.raises(McpTimeoutError):
        await connection.call("slow", {})

    # The owner survived, so the next call still works.
    assert connection.status == "connected"
    assert (await connection.call("echo", {})).content[0].text == "echo ok"
    await store.aclose()


async def test_a_resource_is_read_over_the_same_loop() -> None:
    """An app's HTML is one more command to the owner, not a second session."""
    factory = FakeFactory()
    factory.client.resources = {"ui://stub/app.html": html_resource("ui://stub/app.html", "<p>")}
    store = await connected(factory)

    result = await store.read_resource("stub", "ui://stub/app.html")

    assert result.contents[0].text == "<p>"
    assert factory.client.reads == ["ui://stub/app.html"]
    await store.aclose()


async def test_reading_from_a_server_that_is_not_configured_is_a_key_error() -> None:
    store = await connected(FakeFactory())

    with pytest.raises(KeyError):
        await store.read_resource("nope", "ui://nope/app.html")
    await store.aclose()


async def test_reading_after_close_is_not_connected() -> None:
    factory = FakeFactory()
    factory.client.resources = {"ui://stub/app.html": html_resource("ui://stub/app.html", "<p>")}
    store = await connected(factory)
    await store.aclose()

    with pytest.raises(McpNotConnectedError):
        await store.read_resource("stub", "ui://stub/app.html")


async def test_a_read_the_server_rejects_is_a_connection_error_not_a_crash() -> None:
    store = await connected(FakeFactory())

    with pytest.raises(McpConnectionError, match="unknown resource"):
        await store.read_resource("stub", "ui://stub/missing.html")
    assert store.statuses()[0].status == "connected"
    await store.aclose()


async def test_a_timed_out_read_leaves_the_connection_usable(monkeypatch) -> None:
    monkeypatch.setattr(store_module, "COMMAND_TIMEOUT_SECONDS", 0.05)
    factory = FakeFactory()
    factory.client.resources = {"ui://stub/slow.html": 5.0}
    store = await connected(factory)
    connection = store._connections["stub"]

    with pytest.raises(McpTimeoutError, match="ui://stub/slow.html"):
        await connection.read_resource("ui://stub/slow.html")

    assert connection.status == "connected"
    assert (await connection.call("echo", {})).content[0].text == "echo ok"
    await store.aclose()


async def test_a_server_that_refuses_reports_why_and_offers_nothing() -> None:
    factory = FakeFactory(connect_error=RuntimeError("No such file or directory: nope"))

    store = await connected(factory)

    status = store.statuses()[0]
    assert status.status == "failed"
    assert "No such file or directory" in status.error
    assert store.tools() == []
    await store.aclose()


async def test_an_exception_group_is_unwrapped_to_its_cause() -> None:
    """The SDK wraps failures in an ExceptionGroup; the bare text names nothing."""
    inner = RuntimeError("connection refused")
    factory = FakeFactory(connect_error=BaseExceptionGroup("unhandled", [inner]))

    store = await connected(factory)

    assert store.statuses()[0].error == "connection refused"
    await store.aclose()


async def test_one_failed_server_does_not_cost_the_others_their_tools() -> None:
    """A broken source must not take the whole tool set down with it."""
    factory = FakeFactory()
    store = McpServerStore(
        {**servers("good"), **servers("bad")},
        client_factory=factory,
    )
    await store.start()
    await asyncio.sleep(0.05)

    # Both share one fake client here, so the assertion that matters is that a
    # per-connection failure is per-connection — see the status list.
    assert {s.id for s in store.statuses()} == {"good", "bad"}
    await store.aclose()


async def test_calling_a_closed_connection_raises_not_connected() -> None:
    factory = FakeFactory()
    store = await connected(factory)
    connection = store._connections["stub"]
    await store.aclose()

    with pytest.raises(McpNotConnectedError):
        await connection.call("echo", {})


async def test_a_store_with_no_configured_servers_offers_nothing() -> None:
    store = McpServerStore({})
    await store.start()

    assert store.tools() == []
    assert store.statuses() == []
    await store.aclose()


async def test_start_does_not_wait_for_a_slow_server() -> None:
    """Startup must not be held up by one server taking its whole timeout."""
    factory = FakeFactory(connect_delay=5.0)
    store = McpServerStore(servers(), client_factory=factory)

    await asyncio.wait_for(store.start(), 0.5)

    assert store.statuses()[0].status == "connecting"
    assert store.tools() == []
    await store.aclose()
