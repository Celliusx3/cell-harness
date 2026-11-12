"""A delivery that fails in a way nobody planned for pauses its schedules instead of retrying."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from harness.bots import ASSISTANT_ID
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.schedule_helpers import tick_and_settle, world

EVERY_MINUTE = "DTSTART:20261112T080000Z\nRRULE:FREQ=MINUTELY"


async def test_a_delivery_that_raises_pauses_its_schedule(tmp_path: Path) -> None:
    _, gateway, runs, _, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("unused"))
    )
    attempts: list[str] = []

    async def raising(chat_id: str, _message: object) -> None:
        attempts.append(chat_id)
        raise RuntimeError("the model seam broke")

    runs.hear_when_free = raising
    schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)
    clock.advance(timedelta(minutes=1))

    await tick_and_settle(scheduler, runs, gateway)
    await tick_and_settle(scheduler, runs, gateway)

    assert attempts == [ASSISTANT_ID]
    assert schedules.schedules()[0].status == "paused"
