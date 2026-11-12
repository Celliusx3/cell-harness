"""After downtime only the latest missed time runs, never sooner than a minute after the last."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from harness.bots import ASSISTANT_ID
from harness.schedules import Scheduler
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.schedule_helpers import (
    reminder_events,
    schedules_in,
    tick_and_settle,
    world,
)

EVERY_MINUTE = "DTSTART:20261112T080000Z\nRRULE:FREQ=MINUTELY"


async def test_ten_missed_minutes_run_once_as_the_latest(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    made = schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)
    assert made.scheduled_at == datetime(2026, 11, 12, 8, 1, tzinfo=UTC)

    clock.advance(timedelta(minutes=10, seconds=20))
    await tick_and_settle(scheduler, runs, gateway)
    await tick_and_settle(scheduler, runs, gateway)

    (event,) = await reminder_events(sessions, ASSISTANT_ID)
    (reminder,) = event.reminders
    assert reminder.occurrence_at == datetime(2026, 11, 12, 8, 10, tzinfo=UTC)
    (moved,) = schedules.schedules()
    assert moved.scheduled_at == datetime(2026, 11, 12, 8, 11, tzinfo=UTC)
    (delivery,) = moved.deliveries
    assert delivery.scheduled_at == reminder.occurrence_at


async def test_a_schedule_waits_a_minute_after_its_last_delivery(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)
    clock.advance(timedelta(minutes=1, seconds=50))
    await tick_and_settle(scheduler, runs, gateway)
    (first,) = schedules.schedules()
    assert first.scheduled_at == datetime(2026, 11, 12, 8, 2, tzinfo=UTC)

    clock.advance(timedelta(seconds=20))
    await tick_and_settle(scheduler, runs, gateway)
    assert len(await reminder_events(sessions, ASSISTANT_ID)) == 1
    assert scheduler._wait_seconds() == 40.0

    clock.advance(timedelta(seconds=40))
    await tick_and_settle(scheduler, runs, gateway)
    events = await reminder_events(sessions, ASSISTANT_ID)
    assert [e.reminders[0].occurrence_at.minute for e in events] == [1, 2]


async def test_a_restart_does_not_repeat_a_delivered_run(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)
    clock.advance(timedelta(minutes=5))
    await tick_and_settle(scheduler, runs, gateway)
    await scheduler.aclose()

    restarted = Scheduler(
        schedules_in(tmp_path, clock),
        runs.bots,
        runs,
        follow=gateway.follow,
        now=clock,
    )
    await tick_and_settle(restarted, runs, gateway)
    clock.advance(timedelta(seconds=30))
    await tick_and_settle(restarted, runs, gateway)

    assert len(await reminder_events(sessions, ASSISTANT_ID)) == 1
