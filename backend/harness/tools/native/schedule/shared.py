"""What every schedule tool shares: the group-chat refusal and how a task is shown."""

from __future__ import annotations

from harness.bots import BotNotFound, GroupService
from harness.schedules import Schedule, ScheduleNotFound, ScheduleService
from harness.schedules.domain.timing import zone_of
from harness.tools.models.outcome import INVALID_ARGUMENTS, REFUSED, Failure
from harness.utc import utc_text

IN_A_GROUP = Failure(REFUSED, "schedules work only in your own chat, not in a group chat")


def in_a_group(groups: GroupService, chat_id: str) -> bool:
    """Whether `chat_id` is a group's chat, or no bot's own chat at all."""
    try:
        return groups.members_of_chat(chat_id).group is not None
    except BotNotFound:
        return True


def own(schedules: ScheduleService, bot_id: str, schedule_id: str) -> Schedule:
    """`bot_id`'s schedule with this id; another bot's is `ScheduleNotFound` too."""
    schedule = schedules.get(schedule_id)
    if schedule.bot_id != bot_id:
        raise ScheduleNotFound(schedule_id)
    return schedule


def not_found(err: ScheduleNotFound) -> Failure:
    """What the model is told for an id it has no schedule by."""
    return Failure(INVALID_ARGUMENTS, str(err))


def shown(schedule: Schedule) -> dict[str, str]:
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


def task(schedule: Schedule) -> dict[str, str | None]:
    """`shown`, with the newest delivered occurrence, for a schedule read back."""
    latest = schedule.deliveries[-1].scheduled_at if schedule.deliveries else None
    return {**shown(schedule), "last_occurrence_at": None if latest is None else utc_text(latest)}
