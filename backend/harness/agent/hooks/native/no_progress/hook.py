"""The same call keeps returning the identical result."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import CompletedCall, Signature
from harness.agent.hooks.chain import ToolHook
from harness.llm.messages import render_text
from harness.tools.definition import Ok, ToolOutcome

NO_PROGRESS_WARN, NO_PROGRESS_BLOCK = 2, 5

NO_PROGRESS_WARNING = (
    "Note: this is the same call to {name} as before, and the result is identical — "
    "{n} times now. Calling it again will not answer differently. "
    "Use the result you already have, or do something else."
)
NO_PROGRESS_REFUSAL = (
    "{name} has returned this identical result for these same arguments {n} times "
    "in this turn, so this call was not run. Use the result you already have, "
    "or do something else."
)


@dataclass(frozen=True)
class NoProgressHook(ToolHook):
    """The same call keeps returning the identical result."""

    warn: int = NO_PROGRESS_WARN
    block: int = NO_PROGRESS_BLOCK

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        last = next((e for e in reversed(prior) if sig.is_same_call(e)), None)
        if last is None or last.failed:
            return None
        identical = _identical_results_in_a_row(sig, last.text, prior)
        if identical + 1 < self.block:
            return None
        return NO_PROGRESS_REFUSAL.format(name=sig.name, n=identical)

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        if not isinstance(outcome, Ok):
            return None
        n = _identical_results_in_a_row(sig, render_text(outcome.content), prior) + 1
        return NO_PROGRESS_WARNING.format(name=sig.name, n=n) if n >= self.warn else None


def _identical_results_in_a_row(sig: Signature, text: str, calls: Sequence[CompletedCall]) -> int:
    """Trailing successes of the signature that said exactly `text`."""
    n = 0
    for entry in reversed(calls):
        if not sig.is_same_call(entry):
            continue
        if entry.failed or entry.text != text:
            break
        n += 1
    return n
