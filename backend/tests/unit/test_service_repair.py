"""Resume repairs a crash; read shows it unrepaired and writes nothing."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import aclosing

import pytest

from harness.agent.events import AgentCompleted
from harness.llm.messages import UserMessage
from harness.session.derive import derive_messages
from harness.session.models import ToolCallEvent, TurnEnd, TurnStart, UserMessageEvent
from harness.session.repair import TOOL_OUTCOME_UNKNOWN
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    hanging_tool,
)
from tests.unit.helpers import drain, durable_service, loop_agent, unanswered_calls


@pytest.fixture
def store(tmp_path) -> SessionService:
    return durable_service(tmp_path / "sessions", prefix="s")


async def crash_during_tool(agent_, session, store, tmp_path) -> SessionService:
    """Simulate `kill -9` while a dispatched tool is running."""
    task = asyncio.create_task(_drive(agent_, session))
    for _ in range(50):
        await asyncio.sleep(0)
        if any(isinstance(e, ToolCallEvent) for e in session.events()):
            break
    else:
        raise AssertionError("the tool was never dispatched")
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return SessionService(JsonlSessionRepository(tmp_path / "sessions"))


async def _drive(agent_, session) -> None:
    async with aclosing(agent_.run("go", session=session)) as events:
        async for _ in events:
            pass


async def test_resume_repairs_a_turn_killed_mid_tool(store, tmp_path) -> None:
    session = await store.create()
    agent_ = loop_agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    resumed = await reopened.resume("s0")

    assert unanswered_calls(derive_messages(resumed.events())) == []


async def test_a_repaired_call_tells_the_model_it_may_have_run(store, tmp_path) -> None:
    session = await store.create()
    agent_ = loop_agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    resumed = await reopened.resume("s0")

    tool_message = derive_messages(resumed.events())[-1]
    assert tool_message.text == TOOL_OUTCOME_UNKNOWN


async def test_resuming_twice_does_not_stack_closers(store, tmp_path) -> None:
    session = await store.create()
    agent_ = loop_agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    once = await reopened.resume("s0")
    twice = await reopened.resume("s0")

    assert len(once.events()) == len(twice.events())


async def test_a_repaired_session_can_take_another_turn(store, tmp_path) -> None:
    session = await store.create()
    agent_ = loop_agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    resumed = await reopened.resume("s0")
    next_client = ScriptedClient(completed("carrying on"))
    events = await drain(
        loop_agent(next_client, checkpoint=reopened.flush).run("what happened?", session=resumed)
    )

    assert events[-1] == AgentCompleted(text="carrying on")
    assert unanswered_calls(next_client.seen) == []


async def test_read_shows_a_crashed_log_unrepaired(store, tmp_path) -> None:
    session = await store.create()
    agent_ = loop_agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    displayed = await reopened.read("s0")

    assert unanswered_calls(derive_messages(displayed.events())) != []


async def test_read_writes_nothing(store, tmp_path) -> None:
    session = await store.create()
    agent_ = loop_agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )
    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    before = len((await reopened.read("s0")).events())

    await reopened.read("s0")

    assert len((await reopened.read("s0")).events()) == before


async def test_the_service_keeps_no_cursor_of_its_own(store, tmp_path) -> None:
    session = await store.create()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    await store.flush(session)

    fresh = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    session.append(TurnEnd(turn=0, reason="completed"))
    await fresh.flush(session)

    assert len((await store.resume("s0")).events()) == 3


async def test_flushing_from_two_services_does_not_duplicate(store, tmp_path) -> None:
    session = await store.create()
    session.append(TurnStart(turn=0))
    session.append(TurnEnd(turn=0, reason="completed"))

    await store.flush(session)
    await SessionService(JsonlSessionRepository(tmp_path / "sessions")).flush(session)

    assert len((await store.resume("s0")).events()) == 2
