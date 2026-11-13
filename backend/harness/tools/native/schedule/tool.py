"""`schedule_create`: a task delivered to the bot's own chat at each occurrence of an RRULE."""

from __future__ import annotations

import json

from harness.bots import GroupService
from harness.schedules import InvalidSchedule, ScheduleService
from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.domain.tool import Tool
from harness.tools.native.schedule.models import ScheduleCreateArgs
from harness.tools.native.schedule.shared import IN_A_GROUP, in_a_group, shown

SCHEDULE_CREATE = "schedule_create"

_DESCRIPTION = (
    "Create a scheduled task. At each occurrence of rrule, prompt is delivered to your own chat "
    "as a scheduled message from the user, and you act on it then. The result includes the task "
    "id and the next occurrence as scheduled_at in UTC and scheduled_at_local in the zone of "
    "rrule. After downtime, only the latest missed occurrence is delivered. Delivery can repeat "
    "after a crash."
)


def schedule_create_tool(
    groups: GroupService, schedules: ScheduleService
) -> Tool[ScheduleCreateArgs]:
    """The tool that makes a schedule for the calling bot, from its own chat only."""

    async def execute(args: ScheduleCreateArgs, context: ToolContext) -> ToolOutcome:
        if in_a_group(groups, context.origin.conversation_id):
            return IN_A_GROUP
        try:
            made = schedules.create(context.origin.bot_id, args.title, args.prompt, args.rrule)
        except InvalidSchedule as err:
            return Failure(INVALID_ARGUMENTS, str(err))
        return Ok(json.dumps(shown(made), ensure_ascii=False))

    return Tool.from_model(
        name=SCHEDULE_CREATE,
        description=_DESCRIPTION,
        args_model=ScheduleCreateArgs,
        execute=execute,
    )
