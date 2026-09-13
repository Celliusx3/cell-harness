"""The same call, over and over, whatever it returns — dsh's `repeat-tool-reminder`."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import CompletedCall, Signature
from harness.agent.hooks.chain import ToolHook
from harness.tools.definition import Ok, ToolOutcome

REPEATED_CALL_NOTES = (3, 5, 8)

REPEATED_CALL_NOTE = (
    "Note: this is call number {n} in a row to {name} with these same arguments. "
    "If you are waiting for something to change, say so; otherwise use what you have."
)


@dataclass(frozen=True)
class RepeatedCallHook(ToolHook):
    """The same call, over and over, whatever it returns. Advisory only; the
    decision stays with the model."""

    notes_at: tuple[int, ...] = REPEATED_CALL_NOTES

    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        return None  # never refuses

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        if not isinstance(outcome, Ok):
            return None
        n = 1  # this call
        for entry in reversed(calls):
            if not sig.matches(entry) or entry.failed:
                break
            n += 1
        return REPEATED_CALL_NOTE.format(name=sig.name, n=n) if n in self.notes_at else None
