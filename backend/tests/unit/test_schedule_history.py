"""Each schedule keeps its newest 200 deliveries, none older than 30 days before the newest."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from harness.bots import ASSISTANT_ID
from harness.schedules.service.schedule_service import MAX_KEPT_DELIVERIES
from tests.unit.schedule_helpers import START, Clock, schedules_in

EVERY_MINUTE = "DTSTART:20261112T080000Z\nRRULE:FREQ=MINUTELY"


def test_history_keeps_the_newest_two_hundred(tmp_path: Path) -> None:
    clock = Clock(START)
    schedules = schedules_in(tmp_path, clock)
    made = schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)

    for _ in range(MAX_KEPT_DELIVERIES + 1):
        clock.advance(timedelta(minutes=1))
        schedules.record_delivery(made.id, clock.at)

    (kept,) = schedules.schedules()
    assert MAX_KEPT_DELIVERIES == 200
    assert len(kept.deliveries) == 200
    assert kept.deliveries[0].delivered_at == START + timedelta(minutes=2)
    assert kept.deliveries[-1].delivered_at == clock.at


def test_history_drops_a_delivery_older_than_thirty_days(tmp_path: Path) -> None:
    clock = Clock(START)
    schedules = schedules_in(tmp_path, clock)
    made = schedules.create(ASSISTANT_ID, "Tick", "Tick.", EVERY_MINUTE)
    clock.advance(timedelta(minutes=1))
    schedules.record_delivery(made.id, clock.at)
    clock.advance(timedelta(days=29))
    schedules.record_delivery(made.id, clock.at)
    clock.advance(timedelta(days=1, minutes=1))
    schedules.record_delivery(made.id, clock.at)

    (kept,) = schedules.schedules()
    assert [d.delivered_at for d in kept.deliveries] == [
        START + timedelta(days=29, minutes=1),
        clock.at,
    ]
