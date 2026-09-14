"""The session store, the durability checkpoint, and the model-visible invariant."""

from __future__ import annotations

import pytest

from harness.llm.messages import UserMessage
from harness.session.derive import derive_messages
from harness.session.models import TurnEnd, TurnStart, UserMessageEvent
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import drain, durable_service, loop_agent


@pytest.fixture
def store(tmp_path) -> SessionService:
    return durable_service(tmp_path / "sessions", prefix="s")


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
    await drain(loop_agent(client, checkpoint=checkpoint).run("hi", session=session))

    # Checkpointed once, after turn/start + user/message + step/start.
    assert seen == [3]
    stored = await store.resume("s0")
    assert any(isinstance(e, UserMessageEvent) for e in stored.events())


async def test_a_turn_survives_the_process_it_ran_in(store, tmp_path) -> None:
    client = ScriptedClient(completed("the answer is 42"))
    session = await store.create()
    await drain(loop_agent(client, checkpoint=store.flush).run("what is it?", session=session))
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
    await drain(loop_agent(client, checkpoint=store.flush).run("first", session=session))
    await store.flush(session)

    resumed = await store.resume("s0")
    client._script = completed("two")
    await drain(loop_agent(client, checkpoint=store.flush).run("second", session=resumed))

    assert [(m.role, m.content) for m in client.seen] == [
        ("user", "first"),
        ("assistant", "one"),
        ("user", "second"),
    ]
    assert [e.turn for e in resumed.events() if isinstance(e, TurnStart)] == [0, 1]
