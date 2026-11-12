"""`Scheduler`: the one task that delivers each schedule as it falls due."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine, Iterable
from datetime import datetime, timedelta

from harness.bots import BotNotFound, BotService
from harness.runs.bot_messages import Follow
from harness.runs.run import settled
from harness.runs.service import RunService
from harness.schedules.models import Schedule
from harness.schedules.service import Now, ScheduleNotFound, ScheduleService
from harness.schedules.timing import latest_at_or_before
from harness.session.models import ScheduleReminder, ScheduleReminders
from harness.session.repository import SessionNotFoundError

logger = logging.getLogger("harness.schedules")

MAX_WAIT_SECONDS = 60.0
DELIVERY_FLOOR_SECONDS = 60

Record = Callable[[str, datetime], None]


class ScheduleBusy(RuntimeError):
    """The schedule's chat already holds a delivery in flight."""

    def __init__(self, schedule_id: str) -> None:
        super().__init__("This schedule's bot is already running it.")
        self.schedule_id = schedule_id


class Scheduler:
    """Delivers each bot's due schedules into its chat as one message, then waits for the next."""

    def __init__(
        self,
        schedules: ScheduleService,
        bots: BotService,
        runs: RunService,
        *,
        follow: Follow,
        now: Now,
    ) -> None:
        self._schedules = schedules
        self._bots = bots
        self._runs = runs
        self._follow = follow
        self._now = now
        self._task: asyncio.Task[None] | None = None
        self._deliveries: set[asyncio.Task[None]] = set()
        self._chats_in_flight: set[str] = set()

    def start(self) -> None:
        """Begin the loop, for a server starting up."""
        self._task = asyncio.create_task(self._loop())

    async def aclose(self) -> None:
        """Stop the loop and every delivery still in flight, for a server shutting down."""
        tasks = {*self._deliveries, *([] if self._task is None else [self._task])}
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._task = None

    async def tick(self) -> None:
        """Start one delivery for each bot chat with schedules due now and none in flight."""
        now = self._now()
        for chat_id, due in self._due_by_chat(now).items():
            heard = ScheduleReminders(reminders=tuple(_reminder(s, now) for s in due))
            self._start(chat_id, heard, self._schedules.record_delivery)

    def run_now(self, schedule_id: str) -> None:
        """Deliver the schedule at once, whatever its status, its next time left where it was."""
        schedule = self._schedules.get(schedule_id)
        chat_id = self._bots.chat_of(schedule.bot_id)
        if chat_id in self._chats_in_flight:
            raise ScheduleBusy(schedule_id)
        reminder = _reminder_at(schedule, self._now())
        heard = ScheduleReminders(reminders=(reminder,))
        self._start(chat_id, heard, self._schedules.record_run_now)

    async def _loop(self) -> None:
        while True:
            self._schedules.changed.clear()
            try:
                await self.tick()
            except Exception:
                logger.exception("a pass over the schedules raised")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._schedules.changed.wait(), self._wait_seconds())

    def _waiting(self) -> Iterable[Schedule]:
        """The active schedules whose chat holds no delivery in flight."""
        return (
            s
            for s in self._schedules.schedules()
            if s.status == "active" and self._bots.chat_of(s.bot_id) not in self._chats_in_flight
        )

    def _due_by_chat(self, now: datetime) -> dict[str, tuple[Schedule, ...]]:
        """The schedules due at `now`, by the chat they are delivered in, in the order made."""
        grouped: dict[str, tuple[Schedule, ...]] = {}
        for schedule in self._waiting():
            if _due_at(schedule) <= now:
                chat_id = self._bots.chat_of(schedule.bot_id)
                grouped = {**grouped, chat_id: (*grouped.get(chat_id, ()), schedule)}
        return grouped

    def _wait_seconds(self) -> float:
        """Until the first waiting schedule is due, capped so a sleeping Mac cannot stretch it."""
        due = [_due_at(s) for s in self._waiting()]
        if not due:
            return MAX_WAIT_SECONDS
        left = (min(due) - self._now()).total_seconds()
        return min(max(left, 0.0), MAX_WAIT_SECONDS)

    def _start(self, chat_id: str, heard: ScheduleReminders, record: Record) -> None:
        """Take `chat_id`'s slot and deliver `heard` in it, each delivery kept by `record`."""
        self._chats_in_flight.add(chat_id)
        self._spawn(self._deliver(chat_id, heard, record))

    def _spawn(self, delivery: Coroutine[None, None, None]) -> None:
        task = asyncio.create_task(delivery)
        self._deliveries.add(task)
        task.add_done_callback(self._deliveries.discard)

    async def _deliver(self, chat_id: str, heard: ScheduleReminders, record: Record) -> None:
        """Hold `chat_id`'s slot while its schedules are delivered and their turn runs."""
        try:
            await self._deliver_in(chat_id, heard, record)
        except Exception:
            logger.exception("delivering schedules into chat %s raised; paused them", chat_id)
            for reminder in heard.reminders:
                with contextlib.suppress(ScheduleNotFound):
                    self._schedules.pause(reminder.schedule_id)
        finally:
            self._chats_in_flight.discard(chat_id)
            self._schedules.changed.set()

    async def _deliver_in(self, chat_id: str, heard: ScheduleReminders, record: Record) -> None:
        """Open the turn once the chat is free, have its chat apps hear it, save, then wait."""
        try:
            run = await self._runs.hear_when_free(chat_id, heard)
        except (BotNotFound, SessionNotFoundError) as err:
            logger.warning("schedules in chat %s ended, its bot is gone: %s", chat_id, err)
            for reminder in heard.reminders:
                self._schedules.end(reminder.schedule_id)
            return
        await self._follow(run)
        for reminder in heard.reminders:
            record(reminder.schedule_id, reminder.occurrence_at)
        await settled(run)


def _due_at(schedule: Schedule) -> datetime:
    """`scheduled_at`, held back until a floor of time has passed since the last delivery."""
    if not schedule.deliveries:
        return schedule.scheduled_at
    floor = schedule.deliveries[-1].delivered_at + timedelta(seconds=DELIVERY_FLOOR_SECONDS)
    return max(schedule.scheduled_at, floor)


def _reminder(schedule: Schedule, now: datetime) -> ScheduleReminder:
    """The occurrence a delivery at `now` carries: the latest due, never before `scheduled_at`."""
    latest = latest_at_or_before(schedule.rrule, now)
    occurrence_at = schedule.scheduled_at if latest is None else max(latest, schedule.scheduled_at)
    return _reminder_at(schedule, occurrence_at)


def _reminder_at(schedule: Schedule, occurrence_at: datetime) -> ScheduleReminder:
    """The reminder that tells the bot `schedule` was due at `occurrence_at`."""
    return ScheduleReminder(
        schedule_id=schedule.id,
        title=schedule.title,
        prompt=schedule.prompt,
        occurrence_at=occurrence_at,
    )
