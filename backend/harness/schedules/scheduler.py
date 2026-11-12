"""`Scheduler`: the one task that delivers each schedule as it falls due."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from harness.bots import BotNotFound, BotService
from harness.runs.bot_messages import Follow
from harness.runs.service import RunService
from harness.schedules.models import Schedule
from harness.schedules.service import Now, ScheduleService
from harness.session.models import ScheduleReminder
from harness.session.repository import SessionNotFoundError

logger = logging.getLogger("harness.schedules")

MAX_WAIT_SECONDS = 60.0


class Scheduler:
    """Delivers every active schedule that is due into its bot's chat, then waits for the next."""

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

    def start(self) -> None:
        """Begin the loop, for a server starting up."""
        self._task = asyncio.create_task(self._loop())

    async def aclose(self) -> None:
        """Stop the loop, for a server shutting down."""
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def tick(self) -> None:
        """Deliver, one after another, every active schedule due now."""
        now = self._now()
        for schedule in self._schedules.schedules():
            if schedule.status == "active" and schedule.scheduled_at <= now:
                await self._deliver(schedule)

    async def _loop(self) -> None:
        while True:
            self._schedules.changed.clear()
            try:
                await self.tick()
            except Exception:
                logger.exception("a pass over the schedules raised")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._schedules.changed.wait(), self._wait_seconds())

    def _wait_seconds(self) -> float:
        """Until the earliest active schedule is due, capped so a sleeping Mac cannot stretch it."""
        due = [s.scheduled_at for s in self._schedules.schedules() if s.status == "active"]
        if not due:
            return MAX_WAIT_SECONDS
        left = (min(due) - self._now()).total_seconds()
        return min(max(left, 0.0), MAX_WAIT_SECONDS)

    async def _deliver(self, schedule: Schedule) -> None:
        """Open the turn in the bot's chat, have its chat apps hear it, then save the schedule."""
        reminder = ScheduleReminder(
            schedule_id=schedule.id,
            title=schedule.title,
            prompt=schedule.prompt,
            occurrence_at=schedule.scheduled_at,
        )
        try:
            chat_id = self._bots.chat_of(schedule.bot_id)
            run = await self._runs.hear_when_free(chat_id, reminder)
        except (BotNotFound, SessionNotFoundError) as err:
            logger.warning("schedule %s ended, its bot is gone: %s", schedule.id, err)
            self._schedules.end(schedule.id)
            return
        await self._follow(run)
        self._schedules.record_delivery(schedule.id, schedule.scheduled_at)
