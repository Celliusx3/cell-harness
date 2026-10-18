"""The same call keeps returning the identical result."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.llm import text_of
from harness.prompts import NO_PROGRESS_REFUSAL, NO_PROGRESS_WARNING
from harness.runtime.hooks.calls import CompletedCall, Signature
from harness.runtime.hooks.service import ToolHook
from harness.tools import Ok, ToolOutcome

NO_PROGRESS_WARN_AT, NO_PROGRESS_BLOCK_AT = 2, 5


@dataclass(frozen=True)
class NoProgressHook(ToolHook):
    """The same call keeps returning the identical result."""

    warn_at: int = NO_PROGRESS_WARN_AT
    block_at: int = NO_PROGRESS_BLOCK_AT

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        last = next((e for e in reversed(prior) if sig.is_same_call(e)), None)
        if last is None or last.failed:
            return None
        identical = _identical_results_in_a_row(sig, last.text, prior)
        if identical + 1 < self.block_at:
            return None
        return NO_PROGRESS_REFUSAL.format(name=sig.name, n=identical)

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        if not isinstance(outcome, Ok):
            return None
        n = _identical_results_in_a_row(sig, text_of(outcome.content), prior) + 1
        return NO_PROGRESS_WARNING.format(name=sig.name, n=n) if n >= self.warn_at else None


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
