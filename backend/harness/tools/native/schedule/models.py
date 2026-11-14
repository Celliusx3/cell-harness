"""What the schedule tools are called with."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20
_ID_DESCRIPTION = "Task id."


class ScheduleCreateArgs(BaseModel):
    """What the model passes to `schedule_create`."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(
        description=(
            "Task name of at most 120 characters in the user's language: action plus object. "
            "Omit timing, status and ids."
        )
    )
    prompt: str = Field(description="Instruction delivered at each occurrence.")
    rrule: str = Field(
        description=(
            "One DTSTART line, a newline, and one RRULE line (RFC 5545). DTSTART ends in Z for "
            "UTC or carries TZID with an IANA time zone; a TZID rule keeps local clock time "
            "across daylight-saving changes. DTSTART may be in the past; delivery starts with "
            "the first occurrence after creation. A one-time delivery is "
            "RRULE:FREQ=DAILY;COUNT=1. No SECONDLY, and BYSECOND takes one value. COUNT is at "
            "most 1000 and cannot be combined with UNTIL; UNTIL is a UTC instant ending in Z. "
            'Example: "DTSTART;TZID=Asia/Singapore:20260901T080000\\nRRULE:FREQ=WEEKLY;'
            'BYDAY=MO,TU,WE,TH,FR"'
        )
    )


class ScheduleListArgs(BaseModel):
    """What the model passes to `schedule_list`."""

    model_config = ConfigDict(frozen=True)

    active: bool | None = Field(
        default=None,
        description=(
            "true for active tasks only; false for paused and ended tasks only; "
            "omitted for all tasks."
        ),
    )
    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Page size from 1 to 50; defaults to 20.",
    )
    offset: int = Field(default=0, ge=0, description="Number of tasks to skip; defaults to 0.")


class ScheduleViewArgs(BaseModel):
    """What the model passes to `schedule_view`."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description=_ID_DESCRIPTION)


class ScheduleEditArgs(BaseModel):
    """What the model passes to `schedule_edit`."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description=_ID_DESCRIPTION)
    action: Literal["update", "delete"] = Field(
        description="update applies the provided fields, at least one; delete removes the task."
    )
    title: str | None = Field(
        default=None,
        description=(
            "New task name of at most 120 characters in the user's language: action plus "
            "object. Omit timing, status and ids."
        ),
    )
    prompt: str | None = Field(
        default=None, description="New instruction delivered at each occurrence."
    )
    rrule: str | None = Field(
        default=None, description="New recurrence in the schedule_create rrule format."
    )
    active: bool | None = Field(
        default=None,
        description="false pauses the task; true resumes it from its next occurrence after now.",
    )
