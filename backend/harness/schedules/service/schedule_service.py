"""`ScheduleService`: making and changing schedules, and recording each occurrence's fate."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from harness.schedules.domain.models import Delivery, Schedule, SchedulesFile
from harness.schedules.domain.timing import InvalidRrule, next_after
from harness.schedules.repository.schedule_repository import ScheduleRepository

MAX_TITLE_CHARS = 120
MAX_KEPT_DELIVERIES = 200
KEPT_DELIVERY_DAYS = 30

Now = Callable[[], datetime]


class InvalidSchedule(ValueError):
    """A schedule that cannot be made, and which argument is why."""


class ScheduleNotFound(LookupError):
    """No schedule has that id."""

    def __init__(self, schedule_id: str) -> None:
        super().__init__(f"no schedule with id {schedule_id!r}")
        self.schedule_id = schedule_id


class ScheduleService:
    """Every bot's schedules, timed by `now`, telling the scheduler when they change."""

    def __init__(self, repository: ScheduleRepository, *, now: Now) -> None:
        self._repository = repository
        self._now = now
        self.changed = asyncio.Event()

    def schedules(self) -> tuple[Schedule, ...]:
        """Every schedule, in the order made."""
        return self._repository.read().schedules

    def of_bot(self, bot_id: str) -> tuple[Schedule, ...]:
        """`bot_id`'s schedules, in the order made."""
        return tuple(s for s in self.schedules() if s.bot_id == bot_id)

    def get(self, schedule_id: str) -> Schedule:
        """The schedule with this id; `ScheduleNotFound` when there is none."""
        return _find(self.schedules(), schedule_id)

    def create(self, bot_id: str, title: str, prompt: str, rrule: str) -> Schedule:
        """A new active schedule for `bot_id`, due at its first occurrence after now."""
        now = self._now()
        schedule = Schedule(
            id=uuid.uuid4().hex,
            bot_id=bot_id,
            title=_checked_title(title),
            prompt=_checked_prompt(prompt),
            rrule=rrule,
            status="active",
            scheduled_at=_first_after(rrule, now),
            created_at=now,
            updated_at=now,
        )
        self._rewrite_all(lambda stored: (*stored, schedule))
        self.changed.set()
        return schedule

    def record_delivery(self, schedule_id: str, occurrence_at: datetime) -> None:
        """The occurrence due at `occurrence_at` was delivered: keep it, then move on, or end."""
        now = self._now()
        delivery = Delivery(scheduled_at=occurrence_at, delivered_at=now)
        self._rewrite_one(schedule_id, lambda schedule: _delivered(schedule, delivery, now))

    def record_run_now(self, schedule_id: str, occurrence_at: datetime) -> None:
        """A run-now delivery: kept, its next time and status left where they were."""
        now = self._now()
        delivery = Delivery(scheduled_at=occurrence_at, delivered_at=now)
        self._rewrite_one(schedule_id, lambda schedule: _with_delivery(schedule, delivery, now))

    def end(self, schedule_id: str) -> None:
        """End the schedule, its `scheduled_at` left where it was."""
        now = self._now()
        self._rewrite_one(
            schedule_id,
            lambda schedule: schedule.model_copy(update={"status": "ended", "updated_at": now}),
        )

    def update(
        self,
        schedule_id: str,
        *,
        title: str | None = None,
        prompt: str | None = None,
        rrule: str | None = None,
    ) -> Schedule:
        """Change the fields given; a new rrule moves `scheduled_at` and revives an ended one."""
        return self._revise_and_notify(
            schedule_id, lambda s, now: _edited(s, now, title, prompt, rrule)
        )

    def pause(self, schedule_id: str) -> Schedule:
        """Stop delivering the schedule until it is resumed."""
        return self._revise_and_notify(
            schedule_id, lambda s, _: s.model_copy(update={"status": "paused"})
        )

    def resume(self, schedule_id: str) -> Schedule:
        """Deliver the schedule again, from its first occurrence after now."""
        return self._revise_and_notify(schedule_id, _resumed)

    def delete(self, schedule_id: str) -> None:
        """Remove the schedule for good."""
        self._rewrite_all(lambda stored: _without(stored, _find(stored, schedule_id)))
        self.changed.set()

    def delete_of_bot(self, bot_id: str) -> None:
        """Remove every schedule of `bot_id`, for a bot deleted for good."""
        self._rewrite_all(lambda stored: tuple(s for s in stored if s.bot_id != bot_id))
        self.changed.set()

    def _revise_and_notify(
        self, schedule_id: str, revise: Callable[[Schedule, datetime], Schedule]
    ) -> Schedule:
        """Replace the schedule with `revise` of it, stamped now, and say the schedules changed."""
        now = self._now()

        def change(stored: tuple[Schedule, ...]) -> tuple[Schedule, ...]:
            revised = revise(_find(stored, schedule_id), now).model_copy(update={"updated_at": now})
            return tuple(revised if s.id == schedule_id else s for s in stored)

        written = self._rewrite_all(change)
        self.changed.set()
        return _find(written, schedule_id)

    def _rewrite_one(self, schedule_id: str, change: Callable[[Schedule], Schedule]) -> None:
        self._rewrite_all(
            lambda stored: tuple(change(s) if s.id == schedule_id else s for s in stored)
        )

    def _rewrite_all(
        self, change: Callable[[tuple[Schedule, ...]], tuple[Schedule, ...]]
    ) -> tuple[Schedule, ...]:
        """Every write: read, change, write, with no await between, so no two changes interleave."""
        changed = change(self._repository.read().schedules)
        self._repository.write(SchedulesFile(schedules=changed))
        return changed


def _find(stored: tuple[Schedule, ...], schedule_id: str) -> Schedule:
    found = next((s for s in stored if s.id == schedule_id), None)
    if found is None:
        raise ScheduleNotFound(schedule_id)
    return found


def _without(stored: tuple[Schedule, ...], gone: Schedule) -> tuple[Schedule, ...]:
    return tuple(s for s in stored if s.id != gone.id)


def _edited(
    schedule: Schedule, now: datetime, title: str | None, prompt: str | None, rrule: str | None
) -> Schedule:
    """`schedule` with each given field checked and set; a new rrule restarts its timing."""
    fields: dict[str, str | datetime] = {}
    if title is not None:
        fields = {**fields, "title": _checked_title(title)}
    if prompt is not None:
        fields = {**fields, "prompt": _checked_prompt(prompt)}
    if rrule is not None:
        fields = {**fields, "rrule": rrule, "scheduled_at": _first_after(rrule, now)}
        fields = fields if schedule.status != "ended" else {**fields, "status": "active"}
    return schedule.model_copy(update=fields)


def _resumed(schedule: Schedule, now: datetime) -> Schedule:
    first = _first_after(schedule.rrule, now)
    return schedule.model_copy(update={"status": "active", "scheduled_at": first})


def _with_delivery(schedule: Schedule, delivery: Delivery, now: datetime) -> Schedule:
    deliveries = _recent_deliveries((*schedule.deliveries, delivery))
    return schedule.model_copy(update={"deliveries": deliveries, "updated_at": now})


def ordered(schedules: tuple[Schedule, ...], active: bool | None) -> tuple[Schedule, ...]:
    """Active by `scheduled_at`, then the rest newest made first, narrowed by `active`."""
    active_by_due = sorted(
        (s for s in schedules if s.status == "active"), key=lambda s: s.scheduled_at
    )
    rest = sorted((s for s in schedules if s.status != "active"), key=lambda s: s.created_at)
    if active is True:
        return tuple(active_by_due)
    newest_first = tuple(reversed(rest))
    return newest_first if active is False else (*active_by_due, *newest_first)


def _delivered(schedule: Schedule, delivery: Delivery, now: datetime) -> Schedule:
    following = next_after(schedule.rrule, now)
    moved = {"status": "ended"} if following is None else {"scheduled_at": following}
    return _with_delivery(schedule, delivery, now).model_copy(update=moved)


def _recent_deliveries(deliveries: tuple[Delivery, ...]) -> tuple[Delivery, ...]:
    """The newest `MAX_KEPT_DELIVERIES`, none more than `KEPT_DELIVERY_DAYS` before the newest."""
    cutoff = deliveries[-1].delivered_at - timedelta(days=KEPT_DELIVERY_DAYS)
    recent = tuple(d for d in deliveries if d.delivered_at >= cutoff)
    return recent[-MAX_KEPT_DELIVERIES:]


def _checked_title(title: str) -> str:
    trimmed = title.strip()
    if not trimmed:
        raise InvalidSchedule("title: must not be empty")
    if len(trimmed) > MAX_TITLE_CHARS:
        raise InvalidSchedule(f"title: must be at most {MAX_TITLE_CHARS} characters")
    return trimmed


def _checked_prompt(prompt: str) -> str:
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
