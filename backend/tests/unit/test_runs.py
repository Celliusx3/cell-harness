"""Runs: a turn that outlives the connection that asked for it."""

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


async def test_a_subscriber_walking_away_does_not_end_the_run(service) -> None:
    runs = run_store(
        service,
        SteppedClient(calls_tool("echo", '{"value": "hi"}'), completed("done")),
        echo_tool(),
    )
    session = await service.create()
    run = runs.start(session, "go")

    stream = subscribe(run, after=0)
    await anext(stream)
    await stream.aclose()

    await asyncio.wait_for(run._outer, timeout=5)
    assert run.settled
    assert [e.reason for e in run.session.events() if isinstance(e, TurnEnd)] == ["completed"]


async def test_a_reconnecting_subscriber_misses_nothing(service) -> None:
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
    assert [e.reason for e in seen if isinstance(e, TurnEnd)] == ["completed"]
    assert any(isinstance(e, ToolResultEvent) for e in seen)


async def test_subscribing_after_the_turn_ends_replays_everything(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    assert await drain(subscribe(run, after=0)) == list(run.session.events())


async def test_a_settled_run_still_yields_its_last_events(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")
    await asyncio.wait_for(run._outer, timeout=5)

    events = await drain(subscribe(run, after=len(run.session.events()) - 1))

    assert [type(e) for e in events] == [TurnEnd]


async def test_a_subscriber_waiting_when_the_run_settles_is_released(service) -> None:
    runs = run_store(service, ScriptedClient(completed("hello")))
    session = await service.create()
    run = runs.start(session, "go")

    collected = await asyncio.wait_for(drain(subscribe(run, after=0)), timeout=5)

    assert collected == list(run.session.events())
    assert run.settled


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
    runs.start(session, "second")


async def test_starting_is_atomic_against_a_concurrent_start(service) -> None:
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


async def test_resume_runs_a_turn_that_starts_with_the_answer(service) -> None:
    client = SteppedClient(calls_tool("ask", '{"value": "?"}', id="c1"), completed("cafés"))
    runs = run_store(service, client, pending_tool())
    session = await service.create()
    first = runs.start(session, "near me?")
    await asyncio.wait_for(first._outer, timeout=5)

    assert runs.active(session.id) is None
    run = runs.resume(session, "c1", Ok(content='{"lat": 3.1}'))
    assert runs.active(session.id) is run
    with pytest.raises(RunAlreadyActive):
        runs.resume(session, "c1", Ok(content="again"))
    await asyncio.wait_for(run._outer, timeout=5)

    assert runs.active(session.id) is None
    stored = await service.read(session.id)
    assert [e.reason for e in stored.events() if e.type == "turn/end"] == ["pending", "completed"]
