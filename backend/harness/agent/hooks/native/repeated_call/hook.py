"""The same call, over and over, whatever it returns — dsh's `repeat-tool-reminder`."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import CompletedCall, Signature
from harness.agent.hooks.chain import ToolHook
from harness.tools.definition import Ok, ToolOutcome

REPEATED_CALL_NOTE_AT = (3, 5, 8)

REPEATED_CALL_NOTE = (
    "Note: this is call number {n} in a row to {name} with these same arguments. "
    "If you are waiting for something to change, say so; otherwise use what you have."
)


@dataclass(frozen=True)
class RepeatedCallHook(ToolHook):
    """The same call, over and over, whatever it returns."""

    notes_at: tuple[int, ...] = REPEATED_CALL_NOTE_AT

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        return None

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        if not isinstance(outcome, Ok):
            return None
        n = 1
        for entry in reversed(prior):
            if not sig.is_same_call(entry) or entry.failed:
                break
            n += 1
        return REPEATED_CALL_NOTE.format(name=sig.name, n=n) if n in self.notes_at else None
