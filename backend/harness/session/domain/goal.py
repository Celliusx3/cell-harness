"""A goal run's events: its start, each team turn's role and task, and how it ended."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

GoalRole = Literal["lead", "member"]
GoalStatus = Literal["done", "needs_you", "blocked", "limit_reached", "stopped", "failed"]


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
