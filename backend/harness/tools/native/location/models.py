"""What `get_location` takes, and the fix the device sends, in OpenClaw's `location.get` words."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NoArgs(BaseModel):
    """`get_location` takes nothing: the position is the device's to give."""


class Location(BaseModel):
    """Where the device says it is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    accuracy_m: float = Field(ge=0.0)
