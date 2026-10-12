"""The same tool keeps failing, whatever it is asked."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness.prompts import SAME_TOOL_FAILURE_REFUSAL, SAME_TOOL_FAILURE_WARNING
from harness.runtime.hooks.calls import (
    CompletedCall,
    Signature,
    failures_since_success,
    last_failure_text,
)
from harness.runtime.hooks.service import ToolHook
from harness.tools.definition import Ok, ToolOutcome

SAME_TOOL_FAILURE_WARN_AT, SAME_TOOL_FAILURE_BLOCK_AT = 3, 8


@dataclass(frozen=True)
class SameToolFailureHook(ToolHook):
    """The same tool keeps failing, whatever it is asked."""

    warn_at: int = SAME_TOOL_FAILURE_WARN_AT
    block_at: int = SAME_TOOL_FAILURE_BLOCK_AT

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        failed = failures_since_success(prior, sig.is_same_tool)
        if failed + 1 < self.block_at:
            return None
        return SAME_TOOL_FAILURE_REFUSAL.format(
            name=sig.name, n=failed, last=last_failure_text(prior, sig.is_same_tool)
        )

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        if isinstance(outcome, Ok):
            return None
        n = failures_since_success(prior, sig.is_same_tool) + 1
        return SAME_TOOL_FAILURE_WARNING.format(name=sig.name, n=n) if n >= self.warn_at else None
