"""The same call keeps returning the identical result."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import CompletedCall, Signature
from harness.agent.hooks.chain import ToolHook
from harness.llm.messages import render_text
from harness.tools.definition import Ok, ToolOutcome

NO_PROGRESS_WARN, NO_PROGRESS_BLOCK = 2, 5

# Observed 2026-09-13: a 12B model ran the identical program twice, received the
# identical result twice, and — with nothing telling it the second was the
# first again — answered with an invented address instead of the next tool.
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
    """The same call keeps returning the identical result.

    Refuses without asking whether the tool has side effects. cell-bot refuses
    only read-only tools, on the grounds that a repeated write may have done
    something; but a tool that answered five identical calls with five
    identical replies in one turn is the model spinning either way, and the
    flag that distinction needs (MCP's `readOnlyHint`) is one most servers do
    not set. The refusal text says the call was not run, so the model can say
    so too.
    """

    warn: int = NO_PROGRESS_WARN
    block: int = NO_PROGRESS_BLOCK

    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        last = next((e for e in reversed(calls) if sig.matches(e)), None)
        if last is None or last.failed:
            return None
        prior = _identical_results(sig, last.text, calls)
        if prior + 1 < self.block:
            return None
        return NO_PROGRESS_REFUSAL.format(name=sig.name, n=prior)

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        if not isinstance(outcome, Ok):
            return None
        n = _identical_results(sig, render_text(outcome.content), calls) + 1
        return NO_PROGRESS_WARNING.format(name=sig.name, n=n) if n >= self.warn else None


def _identical_results(sig: Signature, text: str, calls: Sequence[CompletedCall]) -> int:
    """Trailing successes of the signature that said exactly `text`."""
    n = 0
    for entry in reversed(calls):
        if not sig.matches(entry):
            continue
        if entry.failed or entry.text != text:
            break
        n += 1
    return n
