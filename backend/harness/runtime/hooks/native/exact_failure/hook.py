"""The same tool with the same arguments keeps failing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.prompts import EXACT_FAILURE_REFUSAL, EXACT_FAILURE_WARNING
from harness.runtime.hooks.calls import (
    CompletedCall,
    Signature,
    failures_since_success,
    last_failure_text,
)
from harness.runtime.hooks.service import ToolHook
from harness.tools import Ok, ToolOutcome

EXACT_FAILURE_WARN_AT, EXACT_FAILURE_BLOCK_AT = 2, 5


@dataclass(frozen=True)
class ExactFailureHook(ToolHook):
    """The same tool with the same arguments keeps failing."""

    warn_at: int = EXACT_FAILURE_WARN_AT
    block_at: int = EXACT_FAILURE_BLOCK_AT

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        failed = failures_since_success(prior, sig.is_same_call)
        if failed + 1 < self.block_at:
            return None
        return EXACT_FAILURE_REFUSAL.format(
            name=sig.name, n=failed, last=last_failure_text(prior, sig.is_same_call)
        )

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        if isinstance(outcome, Ok):
            return None
        n = failures_since_success(prior, sig.is_same_call) + 1
        return EXACT_FAILURE_WARNING.format(name=sig.name, n=n) if n >= self.warn_at else None
