"""The `schedule/change` event: a schedule of the chat's bot was changed outside the chat."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ScheduleChangeKind = Literal["updated", "deleted"]


class ScheduleChange(BaseModel):
    """Which schedule changed, its title, and whether it was updated or deleted."""

    model_config = ConfigDict(frozen=True)

    schedule_id: str
    title: str
    change: ScheduleChangeKind


class ScheduleChangeEvent(BaseModel):
    """A schedule changed from Settings, told to its bot's chat for its next step."""

    model_config = ConfigDict(frozen=True)

    type: Literal["schedule/change"] = "schedule/change"
    turn: int
    change: ScheduleChange
