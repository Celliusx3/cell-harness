"""The Schedules page: every bot's schedules, and pausing, resuming, running or deleting one."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from harness.bots import BotService
from harness.runs.service.run_service import RunService
from harness.schedules import Schedule, Scheduler, ScheduleService, ordered
from harness.schedules.router.schemas import ScheduleRow
from harness.session.domain.schedule_change import ScheduleChange, ScheduleChangeKind
from harness.utc import utc_text

logger = logging.getLogger(__name__)


def _row(schedule: Schedule, bot_names: dict[str, str]) -> ScheduleRow:
    """`schedule` for the page; a bot that is gone is named by its id."""
    latest = schedule.deliveries[-1].scheduled_at if schedule.deliveries else None
    return ScheduleRow(
        id=schedule.id,
        bot_id=schedule.bot_id,
        bot_name=bot_names.get(schedule.bot_id, schedule.bot_id),
        title=schedule.title,
        prompt=schedule.prompt,
        rrule=schedule.rrule,
        status=schedule.status,
        scheduled_at=utc_text(schedule.scheduled_at),
        last_occurrence_at=None if latest is None else utc_text(latest),
        created_at=utc_text(schedule.created_at),
    )


class ScheduleRouter:
    """List every bot's schedules, and change one."""

    def __init__(
        self, bots: BotService, schedules: ScheduleService, scheduler: Scheduler, runs: RunService
    ) -> None:
        self._bots = bots
        self._schedules = schedules
        self._scheduler = scheduler
        self._runs = runs
        self.router: APIRouter = APIRouter(prefix="/api/schedules", tags=["schedules"])
        self.router.add_api_route(
            "", self.list_schedules, methods=["GET"], response_model=list[ScheduleRow]
        )
        self._add_change_routes()

    def _add_change_routes(self) -> None:
        """Pausing, resuming, running at once and deleting one schedule."""
        no_content = status.HTTP_204_NO_CONTENT
        self.router.add_api_route(
            "/{schedule_id}/pause", self.pause_schedule, methods=["POST"], status_code=no_content
        )
        self.router.add_api_route(
            "/{schedule_id}/resume", self.resume_schedule, methods=["POST"], status_code=no_content
        )
        self.router.add_api_route(
            "/{schedule_id}/run", self.run_schedule_now, methods=["POST"], status_code=no_content
        )
        self.router.add_api_route(
            "/{schedule_id}", self.delete_schedule, methods=["DELETE"], status_code=no_content
        )

    async def list_schedules(self) -> list[ScheduleRow]:
        named = (*await self._bots.open_active_bots(), *self._bots.archived_bots())
        bot_names = {bot.id: bot.name for bot in named}
        return [_row(s, bot_names) for s in ordered(self._schedules.schedules(), None)]

    async def pause_schedule(self, schedule_id: str) -> Response:
        await self._tell(self._schedules.pause(schedule_id), "updated")
        logger.info("schedule %s paused", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def resume_schedule(self, schedule_id: str) -> Response:
        await self._tell(self._schedules.resume(schedule_id), "updated")
        logger.info("schedule %s resumed", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def run_schedule_now(self, schedule_id: str) -> Response:
        self._scheduler.run_now(schedule_id)
        logger.info("schedule %s run now", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def delete_schedule(self, schedule_id: str) -> Response:
        schedule = self._schedules.get(schedule_id)
        self._schedules.delete(schedule_id)
        await self._tell(schedule, "deleted")
        logger.info("schedule %s deleted", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def _tell(self, schedule: Schedule, change: ScheduleChangeKind) -> None:
        """Tell the schedule's bot, in its own chat, that the page changed it."""
        told = ScheduleChange(schedule_id=schedule.id, title=schedule.title, change=change)
        await self._runs.tell_schedule_change(self._bots.chat_of(schedule.bot_id), told)
