"""What `hand_over` asks the user to do, and whether they did it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

STEP_MAX_LENGTH = 240


class HandOver(BaseModel):
    """What `hand_over` is called with: the one step the user has to do."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: str = Field(
        min_length=1,
        max_length=STEP_MAX_LENGTH,
        description=(
            "What the user needs to do and on which site, in one short sentence; it is shown "
            "on their card."
        ),
    )


class HandOverAnswer(BaseModel):
    """The user's answer: true for I'm done, false for Skip."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finished: bool = Field(strict=True)
