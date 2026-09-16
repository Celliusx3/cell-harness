"""The datum: a fix from the device, in OpenClaw's `location.get` vocabulary
— latitude, longitude, accuracy in metres."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Location(BaseModel):
    """Where the device says it is. Bounded, and nothing extra: a page that
    posts an altitude it was not asked for is refused, not trimmed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    accuracy_m: float = Field(ge=0.0)
