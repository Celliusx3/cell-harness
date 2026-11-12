"""`ScheduleService`: making a schedule, and recording what became of each occurrence."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime

from harness.schedules.models import Delivery, Schedule, SchedulesFile
from harness.schedules.repository import ScheduleRepository
from harness.schedules.timing import InvalidRrule, next_after

MAX_TITLE = 120

Now = Callable[[], datetime]


class InvalidSchedule(ValueError):
    """A schedule that cannot be made, and which argument is why."""


class ScheduleService:
    """Every bot's schedules, timed by `now`, telling the scheduler when they change."""

    def __init__(self, repository: ScheduleRepository, *, now: Now) -> None:
        self._repository = repository
        self._now = now
        self.changed = asyncio.Event()

    def schedules(self) -> tuple[Schedule, ...]:
        """Every schedule, in the order made."""
        return self._repository.read().schedules

    def create(self, bot_id: str, title: str, prompt: str, rrule: str) -> Schedule:
        """A new active schedule for `bot_id`, due at its first occurrence after now."""
        now = self._now()
        schedule = Schedule(
            id=uuid.uuid4().hex,
            bot_id=bot_id,
            title=_title(title),
            prompt=_prompt(prompt),
            rrule=rrule,
            status="active",
            scheduled_at=_first_after(rrule, now),
            created_at=now,
            updated_at=now,
        )
        stored = self._repository.read()
        self._repository.write(SchedulesFile(schedules=(*stored.schedules, schedule)))
        self.changed.set()
        return schedule

    def record_delivery(self, schedule_id: str, scheduled_at: datetime) -> None:
        """The occurrence due at `scheduled_at` was delivered: move to the next, or end."""
        now = self._now()
        delivery = Delivery(scheduled_at=scheduled_at, delivered_at=now)
        self._update(schedule_id, lambda schedule: _delivered(schedule, delivery, now))

    def end(self, schedule_id: str) -> None:
        """End the schedule, its `scheduled_at` left where it was."""
        now = self._now()
        self._update(
            schedule_id,
            lambda schedule: schedule.model_copy(update={"status": "ended", "updated_at": now}),
        )

    def _update(self, schedule_id: str, change: Callable[[Schedule], Schedule]) -> None:
        stored = self._repository.read().schedules
        changed = tuple(change(s) if s.id == schedule_id else s for s in stored)
        self._repository.write(SchedulesFile(schedules=changed))


def _delivered(schedule: Schedule, delivery: Delivery, now: datetime) -> Schedule:
    following = next_after(schedule.rrule, now)
    moved = {"status": "ended"} if following is None else {"scheduled_at": following}
    return schedule.model_copy(update={**moved, "last_delivery": delivery, "updated_at": now})


def _title(title: str) -> str:
    trimmed = title.strip()
    if not trimmed:
        raise InvalidSchedule("title: must not be empty")
    if len(trimmed) > MAX_TITLE:
        raise InvalidSchedule(f"title: must be at most {MAX_TITLE} characters")
    return trimmed


def _prompt(prompt: str) -> str:
    trimmed = prompt.strip()
    if not trimmed:
        raise InvalidSchedule("prompt: must not be empty")
    return trimmed


def _first_after(rrule: str, now: datetime) -> datetime:
    try:
        first = next_after(rrule, now)
    except InvalidRrule as err:
        raise InvalidSchedule(f"rrule: {err.reason}") from err
    if first is None:
        raise InvalidSchedule("rrule: no occurrence after now")
    return first
