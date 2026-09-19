"""Stopping a run, and the turn itself driven through the store."""

from __future__ import annotations

import asyncio

import pytest

from harness.llm.client import LLMClient
from harness.runs.subscribe import subscribe
from harness.session.derive import derive_messages
from harness.session.models import (
    AssistantMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    UserMessageEvent,
)
from harness.session.service import SessionService
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
)
from tests.unit.helpers import drain, durable_service, run_store, unanswered_calls, until


@pytest.fixture
def service(tmp_path) -> SessionService:
    return durable_service(tmp_path / "sessions")


async def test_stop_ends_the_turn_and_answers_every_dispatched_call(service) -> None:
    runs = run_store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
    session = await service.create()
    run = runs.start(session, "go")
    await until(
        lambda: any(isinstance(e, ToolCallEvent) for e in session.events()),
        what="the tool to be dispatched",
    )

    assert await runs.stop(session.id) is True

    assert run.settled
    assert [e.reason for e in session.events() if isinstance(e, TurnEnd)] == ["cancelled"]
    assert unanswered_calls(derive_messages(session.events())) == []


async def test_a_stopped_turn_is_durable(service) -> None:
    runs = run_store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
    session = await service.create()
    runs.start(session, "go")
    await until(
        lambda: any(isinstance(e, ToolCallEvent) for e in session.events()),
        what="the tool to be dispatched",
    )

    await runs.stop(session.id)

    stored = await service.read(session.id)
    assert [e.reason for e in stored.events() if isinstance(e, TurnEnd)] == ["cancelled"]
    assert any(isinstance(e, ToolResultEvent) for e in stored.events())


async def test_a_bug_in_the_loop_still_settles_the_run(service) -> None:

    class RaisingClient(LLMClient):
        """A bug on the far side of the seam, not a provider error."""

        async def stream_completion(self, messages, model, *, tools=None):
            raise RuntimeError("kaboom")
            yield

    runs = run_store(service, RaisingClient())
    session = await service.create()
    run = runs.start(session, "go")

    await asyncio.wait_for(run._outer, timeout=5)

    assert run.settled
    assert runs.active(session.id) is None
    stored = await service.read(session.id)
    assert [e.reason for e in stored.events() if isinstance(e, TurnEnd)] == ["cancelled"]


async def test_stopping_an_idle_conversation_reports_nothing_to_stop(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()

    assert await runs.stop(session.id) is False


async def test_stop_releases_a_waiting_subscriber(service) -> None:
    runs = run_store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
    session = await service.create()
    run = runs.start(session, "go")
    collected = asyncio.create_task(drain(subscribe(run, after=0)))
    await until(
        lambda: any(isinstance(e, ToolCallEvent) for e in session.events()),
        what="the tool to be dispatched",
    )

    await runs.stop(session.id)

    events = await asyncio.wait_for(collected, timeout=5)
    assert events == list(session.events())


async def test_aclose_stops_every_run_durably(service) -> None:
    runs = run_store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
    first = await service.create()
    second = await service.create()
    runs.start(first, "go")
    runs.start(second, "go")
    await until(
        lambda: all(any(isinstance(e, ToolCallEvent) for e in s.events()) for s in (first, second)),
        what="both tools to be dispatched",
    )

    await runs.aclose()

    assert runs.active(first.id) is None
    assert runs.active(second.id) is None
    for session in (first, second):
        stored = await service.read(session.id)
        assert unanswered_calls(derive_messages(stored.events())) == []


async def test_a_run_records_the_conversation_it_was_asked(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "what is it?")
    await asyncio.wait_for(run._outer, timeout=5)

    messages = derive_messages(session.events())
    assert [(m.role, m.content) for m in messages] == [
        ("user", "what is it?"),
        ("assistant", "hello"),
    ]


async def test_a_run_is_durable_without_anyone_subscribing(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    stored = await service.read(session.id)
    assert any(isinstance(e, UserMessageEvent) for e in stored.events())
    assert any(isinstance(e, AssistantMessageEvent) for e in stored.events())


async def test_a_tool_using_turn_streams_through_to_a_subscriber(service) -> None:
    runs = run_store(
        service,
        SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("it is 42")),
        echo_tool(),
    )
    session = await service.create()
    run = runs.start(session, "go")

    events = await asyncio.wait_for(drain(subscribe(run, after=0)), timeout=5)

    assert any(isinstance(e, ToolCallEvent) for e in events)
    assert any(isinstance(e, ToolResultEvent) for e in events)
    assert events == list(session.events())


async def test_the_conversation_id_is_the_session_id(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()

    run = runs.start(session, "go")

    assert run.conversation_id == session.id
    await asyncio.wait_for(run._outer, timeout=5)
