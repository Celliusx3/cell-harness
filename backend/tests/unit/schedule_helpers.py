"""A schedule service on a clock a test moves, kept in a file under the test's folder."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from harness.bots import ASSISTANT_ID
from harness.schedules import Scheduler, ScheduleRepository, ScheduleService
from harness.session.domain.models import ScheduleReminderEvent
from harness.session.service.session_service import SessionService
from harness.tools import Tool, ToolOutcome
from tests.bot_models import save_chat_of
from tests.unit.gateway_helpers import build, settle
from tests.unit.helpers import context_for, no_bots, no_skills

START = datetime.fromisoformat("2026-11-12T08:00:00+00:00")


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


async def world(tmp_path: Path, client, *tools: Tool):
    """A gateway, runs, Assistant's saved chat, and a scheduler on a clock at START."""
    bot, gateway, runs, _, sessions = await build(tmp_path, client, *tools, skills=no_skills())
    bots = no_bots(sessions)
    await save_chat_of(sessions, bots, ASSISTANT_ID)
    clock = Clock(START)
    schedules = schedules_in(tmp_path, clock)
    scheduler = Scheduler(schedules, bots, runs, follow=gateway.follow, now=clock)
    return bot, gateway, runs, sessions, clock, schedules, scheduler


async def delivered(scheduler: Scheduler) -> None:
    """Wait until every delivery the scheduler started has settled and released its chat."""
    async with asyncio.timeout(5):
        while scheduler._deliveries:
            await asyncio.gather(*scheduler._deliveries)


async def tick_and_settle(scheduler: Scheduler, runs, gateway) -> None:
    """One pass, then every delivery it started and every turn they opened, finished."""
    await scheduler.tick()
    await delivered(scheduler)
    await settle(runs, gateway)


async def reminder_events(sessions: SessionService, chat_id: str) -> list[ScheduleReminderEvent]:
    """The schedule reminders logged in `chat_id`, oldest first."""
    events = (await sessions.read(chat_id)).events()
    return [e for e in events if isinstance(e, ScheduleReminderEvent)]


async def ask(
    tool: Tool, chat_id: str = ASSISTANT_ID, bot_id: str = ASSISTANT_ID, **arguments: object
) -> ToolOutcome:
    """`tool` called by `bot_id` from `chat_id` with `arguments`."""
    context = context_for(bot_id=bot_id, conversation_id=chat_id)
    return await tool.invoke(json.dumps(arguments), context=context)
