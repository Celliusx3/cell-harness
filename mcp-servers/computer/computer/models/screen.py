"""The person's screen session: watched, or controlled until a time."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ScreenMode = Literal["view", "control"]


class ScreenSession(BaseModel):
    """The person's screen: watched, or controlled until held_until (UTC)."""

    model_config = ConfigDict(frozen=True)

    mode: ScreenMode
    held_until: datetime | None
