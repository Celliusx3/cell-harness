"""The Schedules page: every bot's schedules, and pausing, resuming, running or deleting one."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import APIRouter, Response, status

from harness.bots import BotService
from harness.runs.service import RunService
from harness.schedules import Schedule, Scheduler, ScheduleService, ordered
from harness.schedules.schemas import ScheduleRow
from harness.session.schedule_change import ScheduleChange, ScheduleChangeKind
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


@dataclass(frozen=True)
class _Page:
    """What the page's changes reach: the bots, their schedules, the scheduler and their chats."""

    bots: BotService
    schedules: ScheduleService
    scheduler: Scheduler
    runs: RunService

    async def tell(self, schedule: Schedule, change: ScheduleChangeKind) -> None:
        """Tell the schedule's bot, in its own chat, that the page changed it."""
        told = ScheduleChange(schedule_id=schedule.id, title=schedule.title, change=change)
        await self.runs.tell_schedule_change(self.bots.chat_of(schedule.bot_id), told)


def _change_routes(router: APIRouter, page: _Page) -> None:
    """Pausing, resuming, running at once and deleting one schedule."""

    @router.post("/{schedule_id}/pause", status_code=status.HTTP_204_NO_CONTENT)
    async def pause_schedule(schedule_id: str) -> Response:
        await page.tell(page.schedules.pause(schedule_id), "updated")
        logger.info("schedule %s paused", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{schedule_id}/resume", status_code=status.HTTP_204_NO_CONTENT)
    async def resume_schedule(schedule_id: str) -> Response:
        await page.tell(page.schedules.resume(schedule_id), "updated")
        logger.info("schedule %s resumed", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{schedule_id}/run", status_code=status.HTTP_204_NO_CONTENT)
    async def run_schedule_now(schedule_id: str) -> Response:
        page.scheduler.run_now(schedule_id)
        logger.info("schedule %s run now", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_schedule(schedule_id: str) -> Response:
        schedule = page.schedules.get(schedule_id)
        page.schedules.delete(schedule_id)
        await page.tell(schedule, "deleted")
        logger.info("schedule %s deleted", schedule_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


def build_router(
    bots: BotService, schedules: ScheduleService, scheduler: Scheduler, runs: RunService
) -> APIRouter:
    """List every bot's schedules, and change one."""
    router = APIRouter(prefix="/api/schedules", tags=["schedules"])

    @router.get("", response_model=list[ScheduleRow])
    async def list_schedules() -> list[ScheduleRow]:
        named = (*await bots.active_bots(), *bots.archived_bots())
        bot_names = {bot.id: bot.name for bot in named}
        return [_row(s, bot_names) for s in ordered(schedules.schedules(), None)]

    _change_routes(router, _Page(bots, schedules, scheduler, runs))
    return router
