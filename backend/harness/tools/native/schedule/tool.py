"""`schedule_create`: a task delivered to the bot's own chat at each occurrence of an RRULE."""

from __future__ import annotations

import json

from harness.bots import BotNotFound, BotService
from harness.schedules import InvalidSchedule, Schedule, ScheduleService
from harness.schedules.timing import utc_text, zone_of
from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import INVALID_ARGUMENTS, REFUSED, Failure, Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.schedule.models import ScheduleCreateArgs

SCHEDULE_CREATE = "schedule_create"

_DESCRIPTION = (
    "Create a scheduled task. At each occurrence of rrule, prompt is delivered to your own chat "
    "as a scheduled message from the user, and you act on it then. The result includes the task "
    "id and the next occurrence as scheduled_at in UTC and scheduled_at_local in the zone of "
    "rrule. After downtime, only the latest missed occurrence is delivered. Delivery can repeat "
    "after a crash."
)
_IN_A_GROUP = Failure(REFUSED, "schedules work only in your own chat, not in a group chat")


def schedule_create_tool(bots: BotService, schedules: ScheduleService) -> Tool[ScheduleCreateArgs]:
    """The tool that makes a schedule for the calling bot, from its own chat only."""

    async def execute(args: ScheduleCreateArgs, context: ToolContext) -> ToolOutcome:
        if _in_a_group(bots, context.origin.conversation_id):
            return _IN_A_GROUP
        try:
            made = schedules.create(context.origin.bot_id, args.title, args.prompt, args.rrule)
        except InvalidSchedule as err:
            return Failure(INVALID_ARGUMENTS, str(err))
        return Ok(json.dumps(_shown(made), ensure_ascii=False))

    return Tool.from_model(
        name=SCHEDULE_CREATE,
        description=_DESCRIPTION,
        args_model=ScheduleCreateArgs,
        execute=execute,
    )


def _in_a_group(bots: BotService, chat_id: str) -> bool:
    """Whether `chat_id` is a group's chat, or no bot's own chat at all."""
    try:
        return bots.members_of_chat(chat_id).group is not None
    except BotNotFound:
        return True


def _shown(schedule: Schedule) -> dict[str, str]:
    """What the model is told about the schedule it made."""
    local = schedule.scheduled_at.astimezone(zone_of(schedule.rrule))
    return {
        "id": schedule.id,
        "title": schedule.title,
        "prompt": schedule.prompt,
        "rrule": schedule.rrule,
        "status": schedule.status,
        "scheduled_at": utc_text(schedule.scheduled_at),
        "scheduled_at_local": local.isoformat(timespec="seconds"),
    }
