"""An event logged into a chat for its next step: durable, told to the app, and no turn opened."""

from __future__ import annotations

import asyncio

from harness.app_events import ChatLoggedAppEvent
from harness.bots import ASSISTANT_ID
from harness.session.models import (
    TicketReport,
    TicketReportEvent,
    ToolCallEvent,
    TurnEnd,
    TurnStart,
)
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed, gated_tool
from tests.unit.helpers import durable_service, run_service

REPORT = TicketReport(
    ticket_id="t1", title="Flights", state="blocked", text="Waits.", question="Allow it?"
)


def reported(turn: int) -> TicketReportEvent:
    return TicketReportEvent(turn=turn, report=REPORT)


async def test_an_event_is_logged_durably_in_the_last_turn_and_opens_none(tmp_path) -> None:
    sessions = durable_service(tmp_path / "sessions")
    model = ScriptedClient(completed("hi"))
    runs = run_service(sessions, model)
    session = await sessions.create(ASSISTANT_ID)
    run = runs.start(session, "hello")
    async with run.condition:
        await run.condition.wait_for(lambda: run.settled)
    published = runs.app_events.subscribe()
    told = asyncio.ensure_future(anext(published))
    await asyncio.sleep(0)

    logged = await runs.log_without_turn(ASSISTANT_ID, reported)

    stored = await sessions.read(ASSISTANT_ID)
    assert logged
    assert stored.events()[-1] == reported(0)
    assert [type(e) for e in stored.events()].count(TurnStart) == 1
    assert runs.active(ASSISTANT_ID) is None
    assert model.calls == 1
    assert await asyncio.wait_for(told, timeout=1) == ChatLoggedAppEvent(chat_id=ASSISTANT_ID)
    await published.aclose()


async def test_a_chat_never_written_logs_nothing(tmp_path) -> None:
    sessions = durable_service(tmp_path / "sessions")
    runs = run_service(sessions, ScriptedClient(completed("hi")))

    assert not await runs.log_without_turn("nowhere", reported)
    assert list((tmp_path / "sessions").glob("*.jsonl")) == []


async def test_while_a_turn_runs_the_event_waits_until_it_ends(tmp_path) -> None:
    release = asyncio.Event()
    sessions = durable_service(tmp_path / "sessions")
    runs = run_service(
        sessions,
        SteppedClient(calls_tool("gate", '{"value": "x"}'), completed("done")),
        gated_tool(release),
    )
    session = await sessions.create(ASSISTANT_ID)
    run = runs.start(session, "hello")
    for _ in range(200):
        if any(isinstance(e, ToolCallEvent) for e in run.session.events()):
            break
        await asyncio.sleep(0.01)

    waiting = asyncio.ensure_future(runs.log_when_free(ASSISTANT_ID, reported))
    await asyncio.sleep(0.05)
    assert not waiting.done()
    assert reported(0) not in run.session.events()
    release.set()

    assert await asyncio.wait_for(waiting, timeout=2)
    stored = await sessions.read(ASSISTANT_ID)
    kinds = [type(e) for e in stored.events()]
    assert stored.events()[-1] == reported(0)
    assert kinds.index(TurnEnd) < len(kinds) - 1
