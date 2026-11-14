"""`schedule_list` and `schedule_view`: a bot reads back its own scheduled tasks."""

from __future__ import annotations

import json

from harness.groups import GroupService
from harness.schedules import ScheduleNotFound, ScheduleService, ordered
from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import Ok, ToolOutcome
from harness.tools.domain.tool import Tool
from harness.tools.native.schedule.models import ScheduleListArgs, ScheduleViewArgs
from harness.tools.native.schedule.shared import (
    OWN_CHAT_ONLY_REFUSAL,
    is_outside_own_chat,
    not_found_failure,
    own_schedule,
    read_back_task_fields,
)

SCHEDULE_LIST = "schedule_list"
SCHEDULE_VIEW = "schedule_view"

_LIST_DESCRIPTION = (
    "List your scheduled tasks. Active tasks come first, ordered by scheduled_at; then paused "
    "and ended ones, newest first."
)
_VIEW_DESCRIPTION = "View one of your scheduled tasks by id."


def schedule_list_tool(groups: GroupService, schedules: ScheduleService) -> Tool[ScheduleListArgs]:
    """The tool that pages through the calling bot's schedules, from its own chat only."""

    async def execute(args: ScheduleListArgs, context: ToolContext) -> ToolOutcome:
        if is_outside_own_chat(groups, context.origin.conversation_id):
            return OWN_CHAT_ONLY_REFUSAL
        listed = ordered(schedules.of_bot(context.origin.bot_id), args.active)
        page = listed[args.offset : args.offset + args.limit]
        listing = {
            "items": [read_back_task_fields(s) for s in page],
            "shown": len(page),
            "total": len(listed),
            "limit": args.limit,
            "offset": args.offset,
        }
        return Ok(json.dumps(listing, ensure_ascii=False))

    return Tool.from_model(
        name=SCHEDULE_LIST,
        description=_LIST_DESCRIPTION,
        args_model=ScheduleListArgs,
        execute=execute,
    )


def schedule_view_tool(groups: GroupService, schedules: ScheduleService) -> Tool[ScheduleViewArgs]:
    """The tool that shows one of the calling bot's schedules, from its own chat only."""

    async def execute(args: ScheduleViewArgs, context: ToolContext) -> ToolOutcome:
        if is_outside_own_chat(groups, context.origin.conversation_id):
            return OWN_CHAT_ONLY_REFUSAL
        try:
            found = own_schedule(schedules, context.origin.bot_id, args.id)
        except ScheduleNotFound as err:
            return not_found_failure(err)
        return Ok(json.dumps(read_back_task_fields(found), ensure_ascii=False))

    return Tool.from_model(
        name=SCHEDULE_VIEW,
        description=_VIEW_DESCRIPTION,
        args_model=ScheduleViewArgs,
        execute=execute,
    )
