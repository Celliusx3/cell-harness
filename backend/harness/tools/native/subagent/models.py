"""What `run_subagent` is called with, and how each subagent's turn ended."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

MAX_SUBAGENTS = 4


class SubagentTask(BaseModel):
    """One helper's job: a label for its answer, and the task it is given."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        description="A short label for this helper, shown with its answer, e.g. 'aapl'."
    )
    task: str = Field(
        description="The whole task, written to stand alone: the helper sees none of this "
        "conversation."
    )


class SubagentArgs(BaseModel):
    """What the model passes to `run_subagent`."""

    tasks: list[SubagentTask] = Field(
        min_length=1,
        max_length=MAX_SUBAGENTS,
        description="One to four tasks; their helpers run at the same time.",
    )


@dataclass(frozen=True)
class SubagentReply:
    """The subagent's turn completed with this reply."""

    text: str


@dataclass(frozen=True)
class SubagentStop:
    """The subagent's turn ended without a reply, for this reason."""

    reason: str


SubagentOutcome = SubagentReply | SubagentStop
