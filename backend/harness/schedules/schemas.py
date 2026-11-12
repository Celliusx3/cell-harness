"""The schedules page's request and response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.schedules import ScheduleStatus


class ScheduleRow(BaseModel):
    """One schedule as the page lists it, its times in ISO UTC."""

    model_config = ConfigDict(frozen=True)

    id: str
    bot_id: str
    bot_name: str
    title: str
    prompt: str
    rrule: str
    status: ScheduleStatus
    scheduled_at: str
    last_occurrence_at: str | None
    created_at: str
