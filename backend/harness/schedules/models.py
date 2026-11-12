"""What a schedule is, and the file that keeps every bot's schedules."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ScheduleStatus = Literal["active", "paused", "ended"]


class Delivery(BaseModel):
    """One occurrence handed to the bot's chat: when it was due, and when it was delivered."""

    model_config = ConfigDict(frozen=True)

    scheduled_at: datetime
    delivered_at: datetime


class Schedule(BaseModel):
    """A bot's task: its next undelivered occurrence, and its deliveries oldest first."""

    model_config = ConfigDict(frozen=True)

    id: str
    bot_id: str
    title: str
    prompt: str
    rrule: str
    status: ScheduleStatus
    scheduled_at: datetime
    created_at: datetime
    updated_at: datetime
    deliveries: tuple[Delivery, ...] = ()


class SchedulesFile(BaseModel):
    """The schedules file: every schedule, in the order made."""

    model_config = ConfigDict(frozen=True)

    schedules: tuple[Schedule, ...] = ()
