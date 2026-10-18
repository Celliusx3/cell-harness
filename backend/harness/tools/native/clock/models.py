"""What `get_current_time` is called with."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ClockArgs(BaseModel):
    """Arguments for `get_current_time`."""

    timezone: str = Field(
        default="UTC",
        description="IANA timezone name, e.g. 'Asia/Singapore' or 'UTC'.",
    )
