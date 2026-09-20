"""The model replied with nothing: no text, no tool call."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import CompletedCall
from harness.agent.hooks.chain import GiveUp, StepDecision, StepHook, Tell

EMPTY_REPLY_TELL, EMPTY_REPLY_FAIL = 1, 2

EMPTY_REPLY_NOTE = (
    "Your last reply was empty: no text and no tool call. Answer the user's last "
    "message now, in words, or call the tool you need."
)
EMPTY_REPLY = "the model returned no text, and again after being told"


@dataclass(frozen=True)
class EmptyReplyHook(StepHook):
    """Told once, then the turn fails."""

    tell: int = EMPTY_REPLY_TELL
    fail: int = EMPTY_REPLY_FAIL

    async def end_of_step(
        self, empties: int, prior: Sequence[CompletedCall]
    ) -> StepDecision | None:
        if empties >= self.fail:
            return GiveUp(EMPTY_REPLY)
        if empties >= self.tell:
            return Tell(EMPTY_REPLY_NOTE)
        return None
