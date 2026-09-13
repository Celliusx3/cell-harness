"""The same tool keeps failing, whatever it is asked."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import CompletedCall, Signature
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

    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        prior = _failures_since_success(calls, sig.same_tool)
        if prior + 1 < self.block:
            return None
        return SAME_TOOL_FAILURE_REFUSAL.format(
            name=sig.name, n=prior, last=_last_failure(calls, sig.same_tool)
        )

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        if isinstance(outcome, Ok):
            return None
        n = _failures_since_success(calls, sig.same_tool) + 1
        return SAME_TOOL_FAILURE_WARNING.format(name=sig.name, n=n) if n >= self.warn else None


def _failures_since_success(
    calls: Sequence[CompletedCall], match: Callable[[CompletedCall], bool]
) -> int:
    """How many matching calls have failed since one last succeeded."""
    n = 0
    for entry in reversed(calls):
        if not match(entry):
            continue
        if not entry.failed:
            break
        n += 1
    return n


def _last_failure(calls: Sequence[CompletedCall], match: Callable[[CompletedCall], bool]) -> str:
    """The most recent matching failure's own words — carried into a refusal so
    its advice survives. A `REFUSED` result's "read its schema first" is the
    one line that unsticks that model."""
    return next((e.text for e in reversed(calls) if match(e) and e.failed), "")
