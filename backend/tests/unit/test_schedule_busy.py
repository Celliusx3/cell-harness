"""A schedule due while its chat is busy waits its turn, and is not started twice meanwhile."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

from harness.bots import ASSISTANT_ID
from harness.session.domain.models import ScheduleReminderEvent, TurnEnd
from tests.unit.fakes import SteppedClient, calls_tool, completed, gated_tool
from tests.unit.gateway_helpers import settle
from tests.unit.schedule_helpers import delivered, reminder_events, tick_and_settle, world

EVERY_MINUTE = "DTSTART:20261112T080000Z\nRRULE:FREQ=MINUTELY"
GATE = calls_tool("gate", '{"value": "x"}')


async def until_active(runs, chat_id: str) -> None:
    async with asyncio.timeout(2):
        while runs.active_run(chat_id) is None:
            await asyncio.sleep(0.01)


async def test_a_schedule_due_in_a_busy_chat_runs_once_after_it_settles(tmp_path: Path) -> None:
    release = asyncio.Event()
    client = SteppedClient(GATE, completed("Busy done."), completed("Tick done."))
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, client, gated_tool(release)
    )
    busy = runs.start(await sessions.resume(ASSISTANT_ID), "work")
    await until_active(runs, ASSISTANT_ID)
    schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)
    clock.advance(timedelta(minutes=1, seconds=10))

    await asyncio.wait_for(scheduler.tick(), timeout=1)
    await asyncio.wait_for(scheduler.tick(), timeout=1)
    await asyncio.sleep(0.05)
    assert runs.active_run(ASSISTANT_ID) is busy
    assert schedules.schedules()[0].deliveries == ()

    release.set()
    await delivered(scheduler)
    await settle(runs, gateway)
    await tick_and_settle(scheduler, runs, gateway)

    events = (await sessions.read(ASSISTANT_ID)).events()
    kinds = [type(e) for e in events if isinstance(e, (ScheduleReminderEvent, TurnEnd))]
    assert kinds == [TurnEnd, ScheduleReminderEvent, TurnEnd]
    assert len(schedules.schedules()[0].deliveries) == 1


async def test_a_schedule_whose_run_is_in_flight_is_not_delivered_again(tmp_path: Path) -> None:
    release = asyncio.Event()
    client = SteppedClient(GATE, completed("Tick done."))
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, client, gated_tool(release)
    )
    schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)
    clock.advance(timedelta(minutes=1, seconds=10))
    await scheduler.tick()
    await until_active(runs, ASSISTANT_ID)
    clock.advance(timedelta(minutes=3))

    await scheduler.tick()
    await asyncio.sleep(0.05)
    assert len(await reminder_events(sessions, ASSISTANT_ID)) == 1
    assert len(scheduler._deliveries) == 1
    assert scheduler._wait_seconds() == 60.0

    release.set()
    await delivered(scheduler)
    await settle(runs, gateway)
    assert schedules.changed.is_set()
    await tick_and_settle(scheduler, runs, gateway)

    events = await reminder_events(sessions, ASSISTANT_ID)
    assert [e.reminders[0].occurrence_at.minute for e in events] == [1, 4]
