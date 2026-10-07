"""The model replied with nothing: no text, no tool call."""

from __future__ import annotations

from dataclasses import dataclass

from harness.agent.hooks.service import GiveUp, StepDecision, StepHook, Tell

EMPTY_REPLY_TELL_AT, EMPTY_REPLY_FAIL_AT = 1, 2

EMPTY_REPLY_NOTE = (
    "Your last reply was empty: no text and no tool call. Answer the user's last "
    "message now, in words, or call the tool you need."
)
EMPTY_REPLY = "the model returned no text, and again after being told"


@dataclass(frozen=True)
class EmptyReplyHook(StepHook):
    """Told once, then the turn fails."""

    tell_at: int = EMPTY_REPLY_TELL_AT
    fail_at: int = EMPTY_REPLY_FAIL_AT

    async def end_of_step(self, empties: int) -> StepDecision | None:
        if empties >= self.fail_at:
            return GiveUp(EMPTY_REPLY)
        if empties >= self.tell_at:
            return Tell(EMPTY_REPLY_NOTE)
        return None
