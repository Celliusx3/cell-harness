"""Runs: a turn that outlives the connection that asked for it.

The contract this phase exists to uphold is one line long — *a subscriber walking
away must not end the run* — and most of what follows is that line approached from
different angles.
"""

from __future__ import annotations

import asyncio

import pytest

from harness.runs.store import RunAlreadyActive
from harness.runs.subscribe import subscribe
from harness.session.models import (
    ToolResultEvent,
    TurnEnd,
)
from harness.session.service import SessionService
from harness.tools.definition import Ok
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    pending_tool,
)
from tests.unit.helpers import drain, durable_service, run_store


@pytest.fixture
def service(tmp_path) -> SessionService:
    return durable_service(tmp_path / "sessions")


# ── the central contract ──────────────────────────────────────────────────────


async def test_a_subscriber_walking_away_does_not_end_the_run(service) -> None:
    """The phase in one test.

    A closed tab must not kill the turn, so `subscribe` is abandoned mid-stream
    and the run is expected to finish anyway.
    """
    runs = run_store(
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
    runs = run_store(
        service,
        SteppedClient(calls_tool("echo", '{"value": "hi"}'), completed("done")),
        echo_tool(),
    )
    session = await service.create()
    run = runs.start(session, "go")

    first = subscribe(run, after=0)
    early = [await anext(first), await anext(first)]
    await first.aclose()

    rest = await drain(subscribe(run, after=len(early)))

    seen = [*early, *rest]
    assert seen == list(run.session.events())
    # Asserted explicitly, because comparing against the log alone would pass
    # just as happily on a turn that died halfway.
    assert [e.reason for e in seen if isinstance(e, TurnEnd)] == ["completed"]
    assert any(isinstance(e, ToolResultEvent) for e in seen)


async def test_subscribing_after_the_turn_ends_replays_everything(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    assert await drain(subscribe(run, after=0)) == list(run.session.events())


async def test_a_settled_run_still_yields_its_last_events(service) -> None:
    """`settled` is set *after* the loop's `finally` appends.

    Returning on the flag alone would drop the partial reply, the results for
    abandoned calls, and `turn/end` — the entire record of how a turn ended.
    """
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    events = await drain(subscribe(run, after=len(run.session.events()) - 1))

    assert [type(e) for e in events] == [TurnEnd]


async def test_a_subscriber_waiting_when_the_run_settles_is_released(service) -> None:
    """The two-read race, from the subscriber's side.

    Reading "no new events" and "still running" as two separate questions lets a
    run settle in between, and the subscriber waits for a notify that never comes.
    """
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")

    # Attach, drain to the end of what exists, then park on the condition.
    collected = await asyncio.wait_for(drain(subscribe(run, after=0)), timeout=5)

    assert collected == list(run.session.events())
    assert run.settled


# ── one run per conversation ──────────────────────────────────────────────────


async def test_a_second_run_on_one_conversation_is_refused(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    runs.start(session, "first")

    with pytest.raises(RunAlreadyActive):
        runs.start(session, "second")


async def test_a_conversation_is_free_again_once_its_turn_settles(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
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
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()

    async def attempt() -> str:
        try:
            runs.start(session, "go")
            return "started"
        except RunAlreadyActive:
            return "refused"

    outcomes = await asyncio.gather(attempt(), attempt(), attempt())

    assert sorted(outcomes) == ["refused", "refused", "started"]


# ── resuming a pending turn ───────────────────────────────────────────────────


async def test_resume_runs_a_turn_that_starts_with_the_answer(service) -> None:
    """A pending turn leaves the conversation free; the answer starts a run
    like a message does, and the model continues from the result."""
    client = SteppedClient(calls_tool("ask", '{"value": "?"}', id="c1"), completed("cafés"))
    runs = run_store(service, client, pending_tool())
    session = await service.create()
    first = runs.start(session, "near me?")
    await asyncio.wait_for(first._outer, timeout=5)

    assert runs.active(session.id) is None  # pending is not running
    run = runs.resume(session, "c1", Ok(content='{"lat": 3.1}'))
    assert runs.active(session.id) is run
    with pytest.raises(RunAlreadyActive):
        runs.resume(session, "c1", Ok(content="again"))
    await asyncio.wait_for(run._outer, timeout=5)

    assert runs.active(session.id) is None
    stored = await service.read(session.id)
    assert [e.reason for e in stored.events() if e.type == "turn/end"] == ["pending", "completed"]
