"""`schedule_edit`: a bot changes, pauses, resumes or deletes one of its own scheduled tasks."""

from __future__ import annotations

import json

from harness.bots import GroupService
from harness.schedules import InvalidSchedule, Schedule, ScheduleNotFound, ScheduleService
from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import INVALID_ARGUMENTS, Failure, Ok, ToolOutcome
from harness.tools.domain.tool import Tool
from harness.tools.native.schedule.models import ScheduleEditArgs
from harness.tools.native.schedule.shared import (
    IN_A_GROUP,
    is_outside_own_chat,
    not_found,
    own,
    task,
)

SCHEDULE_EDIT = "schedule_edit"

_DESCRIPTION = (
    "Update, pause, resume, or delete one of your scheduled tasks by id. Deleting does not "
    "retract a reminder already delivered."
)
_NOTHING_TO_UPDATE = Failure(
    INVALID_ARGUMENTS, "update needs at least one of title, prompt, rrule, active"
)


def schedule_edit_tool(groups: GroupService, schedules: ScheduleService) -> Tool[ScheduleEditArgs]:
    """The tool that changes or deletes one of the calling bot's schedules, from its own chat."""

    async def execute(args: ScheduleEditArgs, context: ToolContext) -> ToolOutcome:
        if is_outside_own_chat(groups, context.origin.conversation_id):
            return IN_A_GROUP
        try:
            own(schedules, context.origin.bot_id, args.id)
            return _applied(schedules, args)
        except ScheduleNotFound as err:
            return not_found(err)
        except InvalidSchedule as err:
            return Failure(INVALID_ARGUMENTS, str(err))

    return Tool.from_model(
        name=SCHEDULE_EDIT,
        description=_DESCRIPTION,
        args_model=ScheduleEditArgs,
        execute=execute,
    )


def _applied(schedules: ScheduleService, args: ScheduleEditArgs) -> ToolOutcome:
    if args.action == "delete":
        schedules.delete(args.id)
        return Ok(json.dumps({"id": args.id, "deleted": True}))
    if (args.title, args.prompt, args.rrule, args.active) == (None, None, None, None):
        return _NOTHING_TO_UPDATE
    return Ok(json.dumps(task(_updated(schedules, args)), ensure_ascii=False))


def _updated(schedules: ScheduleService, args: ScheduleEditArgs) -> Schedule:
    """The fields first, then the pause or resume; a refused field changes nothing."""
    edited = (
        schedules.get(args.id)
        if (args.title, args.prompt, args.rrule) == (None, None, None)
        else schedules.update(args.id, title=args.title, prompt=args.prompt, rrule=args.rrule)
    )
    if args.active is False:
        return schedules.pause(args.id)
    if args.active is True:
        return schedules.resume(args.id)
    return edited
