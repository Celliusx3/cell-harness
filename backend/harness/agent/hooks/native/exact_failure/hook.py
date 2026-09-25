"""The same tool with the same arguments keeps failing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import (
    CompletedCall,
    Signature,
    failures_since_success,
    last_failure_text,
)
from harness.agent.hooks.chain import ToolHook
from harness.tools.definition import Ok, ToolOutcome

EXACT_FAILURE_WARN, EXACT_FAILURE_BLOCK = 2, 5

NEXT_STEP = "Change the arguments, use another tool, or tell the user what is blocking you."

EXACT_FAILURE_WARNING = (
    "Note: {name} has now failed {n} times in this turn with these same arguments. "
    "Repeating it unchanged will not help. " + NEXT_STEP
)
EXACT_FAILURE_REFUSAL = (
    "{name} has already failed {n} times in this turn with these same arguments, "
    "most recently: {last}. This call was not run. " + NEXT_STEP
)


@dataclass(frozen=True)
class ExactFailureHook(ToolHook):
    """The same tool with the same arguments keeps failing."""

    warn: int = EXACT_FAILURE_WARN
    block: int = EXACT_FAILURE_BLOCK

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        failed = failures_since_success(prior, sig.matches)
        if failed + 1 < self.block:
            return None
        return EXACT_FAILURE_REFUSAL.format(
            name=sig.name, n=failed, last=last_failure_text(prior, sig.matches)
        )

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        if isinstance(outcome, Ok):
            return None
        n = failures_since_success(prior, sig.matches) + 1
        return EXACT_FAILURE_WARNING.format(name=sig.name, n=n) if n >= self.warn else None
