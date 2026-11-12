"""What `schedule_create` is called with."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
