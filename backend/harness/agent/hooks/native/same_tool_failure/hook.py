"""The same tool keeps failing, whatever it is asked."""

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
from harness.agent.hooks.native.exact_failure.hook import NEXT_STEP
from harness.tools.definition import Ok, ToolOutcome

SAME_TOOL_FAILURE_WARN, SAME_TOOL_FAILURE_BLOCK = 3, 8

SAME_TOOL_FAILURE_WARNING = (
    "Note: {name} has now failed {n} times in this turn across different arguments. "
    "It may not be able to do what you are asking. " + NEXT_STEP
)
SAME_TOOL_FAILURE_REFUSAL = (
    "{name} has already failed {n} times in this turn across different arguments, "
    "most recently: {last}. This call was not run. " + NEXT_STEP
)


@dataclass(frozen=True)
class SameToolFailureHook(ToolHook):
    """The same tool keeps failing, whatever it is asked."""

    warn: int = SAME_TOOL_FAILURE_WARN
    block: int = SAME_TOOL_FAILURE_BLOCK

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        failed = failures_since_success(prior, sig.same_tool)
        if failed + 1 < self.block:
            return None
        return SAME_TOOL_FAILURE_REFUSAL.format(
            name=sig.name, n=failed, last=last_failure_text(prior, sig.same_tool)
        )

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        if isinstance(outcome, Ok):
            return None
        n = failures_since_success(prior, sig.same_tool) + 1
        return SAME_TOOL_FAILURE_WARNING.format(name=sig.name, n=n) if n >= self.warn else None
