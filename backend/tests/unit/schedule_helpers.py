"""A schedule service on a clock a test moves, kept in a file under the test's folder."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from harness.schedules import ScheduleRepository, ScheduleService


class Clock:
    """A `now` that stays put until the test moves it."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at

    def advance(self, by: timedelta) -> None:
        self.at = self.at + by


def schedules_in(tmp_path: Path, clock: Clock) -> ScheduleService:
    """Schedules kept in `schedules.json` under `tmp_path`, timed by `clock`."""
    return ScheduleService(ScheduleRepository(tmp_path / "schedules.json"), now=clock)
