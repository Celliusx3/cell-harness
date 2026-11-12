"""`schedule_list` and `schedule_view`: a bot reads back its own scheduled tasks."""

from __future__ import annotations

import json

from harness.bots import BotService
from harness.schedules import Schedule, ScheduleNotFound, ScheduleService
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.schedule.models import ScheduleListArgs, ScheduleViewArgs
from harness.tools.native.schedule.shared import IN_A_GROUP, in_a_group, not_found, own, task

SCHEDULE_LIST = "schedule_list"
SCHEDULE_VIEW = "schedule_view"

_LIST_DESCRIPTION = (
    "List your scheduled tasks. Active tasks come first, ordered by scheduled_at; then paused "
    "and ended ones, newest first."
)
_VIEW_DESCRIPTION = "View one of your scheduled tasks by id."


def schedule_list_tool(bots: BotService, schedules: ScheduleService) -> Tool[ScheduleListArgs]:
    """The tool that pages through the calling bot's schedules, from its own chat only."""

    async def execute(args: ScheduleListArgs, context: ToolContext) -> ToolOutcome:
        if in_a_group(bots, context.origin.conversation_id):
            return IN_A_GROUP
        listed = _ordered(schedules.of_bot(context.origin.bot_id), args.active)
        page = listed[args.offset : args.offset + args.limit]
        shown = {
            "items": [task(s) for s in page],
            "shown": len(page),
            "total": len(listed),
            "limit": args.limit,
            "offset": args.offset,
        }
        return Ok(json.dumps(shown, ensure_ascii=False))

    return Tool.from_model(
        name=SCHEDULE_LIST,
        description=_LIST_DESCRIPTION,
        args_model=ScheduleListArgs,
        execute=execute,
    )


def schedule_view_tool(bots: BotService, schedules: ScheduleService) -> Tool[ScheduleViewArgs]:
    """The tool that shows one of the calling bot's schedules, from its own chat only."""

    async def execute(args: ScheduleViewArgs, context: ToolContext) -> ToolOutcome:
        if in_a_group(bots, context.origin.conversation_id):
            return IN_A_GROUP
        try:
            found = own(schedules, context.origin.bot_id, args.id)
        except ScheduleNotFound as err:
            return not_found(err)
        return Ok(json.dumps(task(found), ensure_ascii=False))

    return Tool.from_model(
        name=SCHEDULE_VIEW,
        description=_VIEW_DESCRIPTION,
        args_model=ScheduleViewArgs,
        execute=execute,
    )


def _ordered(mine: tuple[Schedule, ...], active: bool | None) -> tuple[Schedule, ...]:
    """Active by `scheduled_at`, then the rest newest made first, narrowed by `active`."""
    running = sorted((s for s in mine if s.status == "active"), key=lambda s: s.scheduled_at)
    rest = sorted((s for s in mine if s.status != "active"), key=lambda s: s.created_at)
    if active is True:
        return tuple(running)
    newest_first = tuple(reversed(rest))
    return newest_first if active is False else (*running, *newest_first)
