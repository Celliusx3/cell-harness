"""The session store, the durability checkpoint, and the model-visible invariant."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import aclosing
from datetime import UTC, datetime

import pytest

from harness.agent.events import AgentCompleted
from harness.agent.loop import LoopAgent
from harness.llm.messages import UserMessage
from harness.session.derive import derive_messages
from harness.session.models import ToolCallEvent, TurnEnd, TurnStart, UserMessageEvent
from harness.session.repair import TOOL_OUTCOME_UNKNOWN
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    hanging_tool,
)
from tests.unit.helpers import unanswered_calls


@pytest.fixture
def store(tmp_path) -> SessionService:
    ids = iter(f"s{n}" for n in range(100))
    return SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )


def agent(client, *tools, checkpoint=None) -> LoopAgent:
    return LoopAgent(
        name="t",
        model="m",
        client=client,
        tools=ToolPipeline(ToolRegistry(tools)) if tools else None,
        checkpoint=checkpoint,
    )


async def drain(gen) -> list:
    return [event async for event in gen]


# ── create and flush ──────────────────────────────────────────────────────────


async def test_a_created_session_is_not_stored_until_it_has_something(store) -> None:
    await store.create()

    assert await store.list() == []


async def test_flush_makes_the_log_durable(store) -> None:
    session = await store.create()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(TurnEnd(turn=0, reason="completed"))

    await store.flush(session)

    assert [h.id for h in await store.list()] == ["s0"]
    resumed = await store.resume("s0")
    assert len(resumed.events()) == 3


async def test_flushing_twice_writes_nothing_the_second_time(store) -> None:
    """The cursor is what keeps `flush` cheap enough to call every request."""
    session = await store.create()
    session.append(TurnStart(turn=0))
    session.append(TurnEnd(turn=0, reason="completed"))
    await store.flush(session)

    await store.flush(session)  # would raise on a non-continuing batch

    resumed = await store.resume("s0")
    assert len(resumed.events()) == 2


async def test_flush_appends_only_the_tail(store) -> None:
    session = await store.create()
    session.append(TurnStart(turn=0))
    await store.flush(session)
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(TurnEnd(turn=0, reason="completed"))

    await store.flush(session)

    assert len((await store.resume("s0")).events()) == 3


# ── the checkpoint, driven by a real turn ─────────────────────────────────────


async def test_a_turn_is_durable_before_its_request_is_sent(store) -> None:
    """The point of the checkpoint: a crash must never leave a reply to a
    question the log cannot show."""
    seen: list[int] = []
    client = ScriptedClient(completed("hello"))

    async def checkpoint(session):
        seen.append(len(session.events()))
        await store.flush(session)

    session = await store.create()
    await drain(agent(client, checkpoint=checkpoint).run("hi", session=session))

    # Checkpointed once, after turn/start + user/message + step/start.
    assert seen == [3]
    stored = await store.resume("s0")
    assert any(isinstance(e, UserMessageEvent) for e in stored.events())


async def test_a_turn_survives_the_process_it_ran_in(store, tmp_path) -> None:
    client = ScriptedClient(completed("the answer is 42"))
    session = await store.create()
    await drain(agent(client, checkpoint=store.flush).run("what is it?", session=session))
    await store.flush(session)

    # A brand-new store over the same directory — nothing shared in memory.
    reopened = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    resumed = await reopened.resume("s0")

    assert [(m.role, m.content) for m in derive_messages(resumed.events())] == [
        ("user", "what is it?"),
        ("assistant", "the answer is 42"),
    ]


async def test_a_resumed_session_continues_its_turn_numbering(store) -> None:
    client = ScriptedClient(completed("one"))
    session = await store.create()
    await drain(agent(client, checkpoint=store.flush).run("first", session=session))
    await store.flush(session)

    resumed = await store.resume("s0")
    client._script = completed("two")
    await drain(agent(client, checkpoint=store.flush).run("second", session=resumed))

    assert [(m.role, m.content) for m in client.seen] == [
        ("user", "first"),
        ("assistant", "one"),
        ("user", "second"),
    ]
    assert [e.turn for e in resumed.events() if isinstance(e, TurnStart)] == [0, 1]


async def crash_during_tool(agent_, session, store, tmp_path) -> SessionService:
    """Simulate `kill -9` while a dispatched tool is running.

    A real crash runs no `finally`, so what matters is **what reached disk**, not
    what the in-memory session later tidied up. So: let the turn run until the
    tool blocks, then read the log back through a fresh store over the same
    directory. Cancelling the task afterwards only unwinds memory — nothing more
    is flushed, so disk keeps exactly the state a dead process would have left.
    """
    task = asyncio.create_task(_drive(agent_, session))
    for _ in range(50):
        await asyncio.sleep(0)
        if any(isinstance(e, ToolCallEvent) for e in session.events()):
            break
    else:  # pragma: no cover - the fixture is broken if this fires
        raise AssertionError("the tool was never dispatched")
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return SessionService(JsonlSessionRepository(tmp_path / "sessions"))


async def _drive(agent_, session) -> None:
    async with aclosing(agent_.run("go", session=session)) as events:
        async for _ in events:
            pass


# ── resume repairs a crash ────────────────────────────────────────────────────


async def test_resume_repairs_a_turn_killed_mid_tool(store, tmp_path) -> None:
    """The phase in one test: a conversation the process died inside is usable."""
    session = await store.create()
    agent_ = agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    resumed = await reopened.resume("s0")

    assert unanswered_calls(derive_messages(resumed.events())) == []


async def test_a_repaired_call_tells_the_model_it_may_have_run(store, tmp_path) -> None:
    """It was dispatched, so it may have completed a side effect. The model is
    told that rather than being told it is safe to retry."""
    session = await store.create()
    agent_ = agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    resumed = await reopened.resume("s0")

    tool_message = derive_messages(resumed.events())[-1]
    assert tool_message.content == TOOL_OUTCOME_UNKNOWN


async def test_resuming_twice_does_not_stack_closers(store, tmp_path) -> None:
    session = await store.create()
    agent_ = agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    once = await reopened.resume("s0")
    twice = await reopened.resume("s0")

    assert len(once.events()) == len(twice.events())


async def test_a_repaired_session_can_take_another_turn(store, tmp_path) -> None:
    """A provider would reject the unrepaired history outright, so this is the
    difference between resume working and resume 400ing."""
    session = await store.create()
    agent_ = agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    resumed = await reopened.resume("s0")
    next_client = ScriptedClient(completed("carrying on"))
    events = await drain(
        agent(next_client, checkpoint=reopened.flush).run("what happened?", session=resumed)
    )

    assert events[-1] == AgentCompleted(text="carrying on")
    assert unanswered_calls(next_client.seen) == []


# ── read is the display path, resume is the write path ────────────────────────


async def test_read_shows_a_crashed_log_unrepaired(store, tmp_path) -> None:
    """A page view renders what happened, not synthetic closers.

    `resume` exists to make a history a provider will accept; `read` exists to
    show a human what the log holds. After a crash those differ, and this is the
    test that pins which one does which.
    """
    session = await store.create()
    agent_ = agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )

    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    displayed = await reopened.read("s0")

    assert unanswered_calls(derive_messages(displayed.events())) != []


async def test_read_writes_nothing(store, tmp_path) -> None:
    """A GET must not mutate the log. `resume` appends its repair; `read` cannot."""
    session = await store.create()
    agent_ = agent(
        SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool(), checkpoint=store.flush
    )
    reopened = await crash_during_tool(agent_, session, store, tmp_path)
    before = len((await reopened.read("s0")).events())

    await reopened.read("s0")

    assert len((await reopened.read("s0")).events()) == before


async def test_the_service_keeps_no_cursor_of_its_own(store, tmp_path) -> None:
    """One cursor, owned by the repository.

    A second `SessionService` over the same directory must pick up exactly where
    the first left off — which is only true if neither is remembering privately.
    """
    session = await store.create()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    await store.flush(session)

    fresh = SessionService(JsonlSessionRepository(tmp_path / "sessions"))
    session.append(TurnEnd(turn=0, reason="completed"))
    await fresh.flush(session)

    assert len((await store.resume("s0")).events()) == 3


async def test_flushing_from_two_services_does_not_duplicate(store, tmp_path) -> None:
    """The failure the old second cursor made possible: each service thinking it
    had flushed a different amount, and one re-appending what the other wrote."""
    session = await store.create()
    session.append(TurnStart(turn=0))
    session.append(TurnEnd(turn=0, reason="completed"))

    await store.flush(session)
    await SessionService(JsonlSessionRepository(tmp_path / "sessions")).flush(session)

    assert len((await store.resume("s0")).events()) == 2
