"""A goal run's events, and the lead's `<goal>` block that only the run reads."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

GoalRole = Literal["lead", "member"]
GoalStatus = Literal["done", "needs_you", "blocked", "limit_reached", "stopped", "failed"]
BLOCK_OPEN = "<goal>"
BLOCK_CLOSE = "</goal>"
_BLOCK = re.compile(r"<goal>.*?</goal>", re.DOTALL)


class GoalStartEvent(BaseModel):
    """The person's `/goal` in `turn` started a run toward `goal`, led by `lead_id`."""

    model_config = ConfigDict(frozen=True)

    type: Literal["goal/start"] = "goal/start"
    turn: int
    goal: str
    lead_id: str
    max_turns: int


class GoalStepEvent(BaseModel):
    """Team turn `step` of the run is `turn`, `bot_id`'s, with the member's task."""

    model_config = ConfigDict(frozen=True)

    type: Literal["goal/step"] = "goal/step"
    turn: int
    bot_id: str
    role: GoalRole
    step: int
    task: str | None
    note: str | None


class GoalEndEvent(BaseModel):
    """The run ended after `turns_used` team turns, for `status`, and why."""

    model_config = ConfigDict(frozen=True)

    type: Literal["goal/end"] = "goal/end"
    turn: int
    status: GoalStatus
    detail: str
    turns_used: int


def without_goal_blocks(text: str) -> str:
    """`text` without any `<goal>` block, nor one cut off at its end; as it was without one."""
    if BLOCK_OPEN not in text:
        return text
    closed = _BLOCK.sub("", text)
    return closed.split(BLOCK_OPEN, 1)[0].strip()
