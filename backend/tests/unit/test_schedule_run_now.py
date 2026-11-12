"""Run now: a schedule delivered at once, its next time and status left where they were."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID
from harness.schedules import ScheduleNotFound
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.gateway_helpers import settle
from tests.unit.schedule_helpers import delivered, reminder_events, world

DAILY = "DTSTART:20261113T090000Z\nRRULE:FREQ=DAILY"


async def test_run_now_delivers_a_paused_schedule_and_keeps_it_paused(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Checked."))
    )
    made = schedules.create(ASSISTANT_ID, "Check", "Check the deployment.", DAILY)
    schedules.pause(made.id)
    clock.advance(timedelta(minutes=5))

    scheduler.run_now(made.id)
    await delivered(scheduler)
    await settle(runs, gateway)

    (kept,) = schedules.schedules()
    assert (kept.status, kept.scheduled_at) == ("paused", made.scheduled_at)
    assert [d.scheduled_at for d in kept.deliveries] == [clock()]
    (heard,) = await reminder_events(sessions, ASSISTANT_ID)
    assert [r.occurrence_at for r in heard.reminders] == [clock()]


async def test_run_now_on_an_unknown_id_is_not_found(tmp_path: Path) -> None:
    *_, scheduler = await world(tmp_path, ScriptedClient(completed("Checked.")))

    with pytest.raises(ScheduleNotFound):
        scheduler.run_now("no-such-schedule")
