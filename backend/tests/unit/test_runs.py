"""Runs: a turn that outlives the connection that asked for it.

The contract this phase exists to uphold is one line long — *a subscriber walking
away must not end the run* — and most of what follows is that line approached from
different angles.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from harness.agent.loop import LoopAgent
from harness.llm.client import LLMClient
from harness.runs.store import RunAlreadyActive, RunStore
from harness.runs.subscribe import subscribe
from harness.session.derive import derive_messages
from harness.session.models import (
    AssistantMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    UserMessageEvent,
)
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
)
from tests.unit.helpers import pipeline_for, unanswered_calls


@pytest.fixture
def service(tmp_path) -> SessionService:
    ids = iter(f"c{n}" for n in range(100))
    return SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )


def store(service: SessionService, client, *tools) -> RunStore:
    agent = LoopAgent(
        name="t",
        model="m",
        client=client,
        tools=pipeline_for(*tools) if tools else None,
        checkpoint=service.flush,
    )
    return RunStore(service, agent)


async def until(predicate, *, what: str) -> None:
    """Let the loop run until `predicate` holds.

    Polling rather than an event, because what is being waited for is a *third
    party's* progress — the loop appending to a log it owns — and there is no
    hook for it that would not exist purely for tests.
    """
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"timed out waiting for {what}")


async def drain(run, *, after: int = 0) -> list:
    return [event async for event in subscribe(run, after=after)]


# ── the central contract ──────────────────────────────────────────────────────


async def test_a_subscriber_walking_away_does_not_end_the_run(service) -> None:
    """The phase in one test.

    A closed tab must not kill the turn, so `subscribe` is abandoned mid-stream
    and the run is expected to finish anyway.
    """
    runs = store(
        service,
        SteppedClient(calls_tool("echo", '{"value": "hi"}'), completed("done")),
        echo_tool(),
    )
    session = await service.create()
    run = runs.start(session, "go")

    stream = subscribe(run, after=0)
    await anext(stream)  # attach, take one event, leave
    await stream.aclose()

    await asyncio.wait_for(run._outer, timeout=5)
    assert run.settled
    assert [e.reason for e in run.session.events() if isinstance(e, TurnEnd)] == ["completed"]


async def test_a_reconnecting_subscriber_misses_nothing(service) -> None:
    """Disconnect, reconnect with the cursor, get every missed event exactly once."""
    runs = store(
        service,
        SteppedClient(calls_tool("echo", '{"value": "hi"}'), completed("done")),
        echo_tool(),
    )
    session = await service.create()
    run = runs.start(session, "go")

    first = subscribe(run, after=0)
    early = [await anext(first), await anext(first)]
    await first.aclose()

    rest = await drain(run, after=len(early))

    seen = [*early, *rest]
    assert seen == list(run.session.events())
    # Asserted explicitly, because comparing against the log alone would pass
    # just as happily on a turn that died halfway.
    assert [e.reason for e in seen if isinstance(e, TurnEnd)] == ["completed"]
    assert any(isinstance(e, ToolResultEvent) for e in seen)


async def test_subscribing_after_the_turn_ends_replays_everything(service) -> None:
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    assert await drain(run) == list(run.session.events())


async def test_a_settled_run_still_yields_its_last_events(service) -> None:
    """`settled` is set *after* the loop's `finally` appends.

    Returning on the flag alone would drop the partial reply, the results for
    abandoned calls, and `turn/end` — the entire record of how a turn ended.
    """
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    events = await drain(run, after=len(run.session.events()) - 1)

    assert [type(e) for e in events] == [TurnEnd]


async def test_a_subscriber_waiting_when_the_run_settles_is_released(service) -> None:
    """The two-read race, from the subscriber's side.

    Reading "no new events" and "still running" as two separate questions lets a
    run settle in between, and the subscriber waits for a notify that never comes.
    """
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")

    # Attach, drain to the end of what exists, then park on the condition.
    collected = await asyncio.wait_for(drain(run), timeout=5)

    assert collected == list(run.session.events())
    assert run.settled


# ── one run per conversation ──────────────────────────────────────────────────


async def test_a_second_run_on_one_conversation_is_refused(service) -> None:
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    runs.start(session, "first")

    with pytest.raises(RunAlreadyActive):
        runs.start(session, "second")


async def test_a_conversation_is_free_again_once_its_turn_settles(service) -> None:
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "first")
    await asyncio.wait_for(run._outer, timeout=5)

    assert runs.active(session.id) is None
    runs.start(session, "second")  # must not raise


async def test_starting_is_atomic_against_a_concurrent_start(service) -> None:
    """Two requests arriving together must produce one turn, not two interleaved.

    `start` is synchronous precisely so the check and the registration cannot be
    split by an await — this is the test that would catch making it `async`.
    """
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()

    async def attempt() -> str:
        try:
            runs.start(session, "go")
            return "started"
        except RunAlreadyActive:
            return "refused"

    outcomes = await asyncio.gather(attempt(), attempt(), attempt())

    assert sorted(outcomes) == ["refused", "refused", "started"]


# ── stopping ──────────────────────────────────────────────────────────────────


async def test_stop_ends_the_turn_and_answers_every_dispatched_call(service) -> None:
    """A stopped turn must leave a history a provider will accept."""
    runs = store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
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
    """A turn stopped mid-tool is on disk, not just tidy in memory.

    Note this passes whichever of the two tasks `stop` cancels — the comment on
    `Run.__init__` explains why, and why the split is kept regardless. A test that
    failed on the swap would have to assert *which* task was cancelled, which pins
    the mechanism rather than the contract.
    """
    runs = store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
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
    """The safety net, deliberately tripped.

    A conversation stuck at "running" forever cannot even be retried — the next
    message is refused as a second run — so an unexpected exception has to end in
    the same settled, deregistered, durable state as success.

    Found by accident: an earlier version of the test above forgot to register the
    tool, the loop's own assertion fired, and this path is what kept the run from
    hanging.
    """

    class RaisingClient(LLMClient):
        """A bug on the far side of the seam, not a provider error.

        A provider failure is `Failed` on the stream and the loop reports it as
        `AgentFailed`. Raising is what a *defect* looks like, and is the only way
        to reach `_drive`'s exception path.
        """

        async def stream_completion(self, messages, model, *, tools=None):
            raise RuntimeError("kaboom")
            yield  # pragma: no cover - unreachable, makes this an async generator

    runs = store(service, RaisingClient())
    session = await service.create()
    run = runs.start(session, "go")

    await asyncio.wait_for(run._outer, timeout=5)

    assert run.settled
    assert runs.active(session.id) is None
    stored = await service.read(session.id)
    assert [e.reason for e in stored.events() if isinstance(e, TurnEnd)] == ["cancelled"]


async def test_stopping_an_idle_conversation_reports_nothing_to_stop(service) -> None:
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()

    assert await runs.stop(session.id) is False


async def test_stop_releases_a_waiting_subscriber(service) -> None:
    runs = store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
    session = await service.create()
    run = runs.start(session, "go")
    collected = asyncio.create_task(drain(run))
    await until(
        lambda: any(isinstance(e, ToolCallEvent) for e in session.events()),
        what="the tool to be dispatched",
    )

    await runs.stop(session.id)

    events = await asyncio.wait_for(collected, timeout=5)
    assert events == list(session.events())


async def test_aclose_stops_every_run_durably(service) -> None:
    """Server shutdown goes through `stop`, so interrupted turns stay resumable."""
    runs = store(service, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool())
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


# ── the turn itself, driven through the store ─────────────────────────────────


async def test_a_run_records_the_conversation_it_was_asked(service) -> None:
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "what is it?")
    await asyncio.wait_for(run._outer, timeout=5)

    messages = derive_messages(session.events())
    assert [(m.role, m.content) for m in messages] == [
        ("user", "what is it?"),
        ("assistant", "hello"),
    ]


async def test_a_run_is_durable_without_anyone_subscribing(service) -> None:
    """Nobody is watching, and the conversation is still there afterwards."""
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    stored = await service.read(session.id)
    assert any(isinstance(e, UserMessageEvent) for e in stored.events())
    assert any(isinstance(e, AssistantMessageEvent) for e in stored.events())


async def test_a_tool_using_turn_streams_through_to_a_subscriber(service) -> None:
    runs = store(
        service,
        SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("it is 42")),
        echo_tool(),
    )
    session = await service.create()
    run = runs.start(session, "go")

    events = await asyncio.wait_for(drain(run), timeout=5)

    assert any(isinstance(e, ToolCallEvent) for e in events)
    assert any(isinstance(e, ToolResultEvent) for e in events)
    assert events == list(session.events())


async def test_the_conversation_id_is_the_session_id(service) -> None:
    """Not a second identity to keep in step."""
    runs = store(service, ScriptedClient(completed("hello")))
    session = await service.create()

    run = runs.start(session, "go")

    assert run.conversation_id == session.id
    await asyncio.wait_for(run._outer, timeout=5)
