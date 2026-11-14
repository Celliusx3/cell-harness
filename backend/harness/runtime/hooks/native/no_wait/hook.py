"""The orchestrator waiting in its own turn for what arrives by itself."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from harness.runtime.hooks.calls import CompletedCall, Signature
from harness.runtime.hooks.service import ToolHook
from harness.tickets.domain.prompts import NO_WAIT_REFUSAL
from harness.tools import ToolOutcome
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT

SHELL_SUFFIX = "__shell"
LONG_TIMEOUT_PATTERN = re.compile(r"setTimeout\([^;]*?,\s*(?:[5-9]\d{3}|[1-9]\d{4,})\s*\)")
SLEEP_COMMAND_PATTERN = re.compile(r"(?:^|[;&|(\n])\s*sleep\s+\d", re.MULTILINE)


def is_waiting_call(name: str, arguments: str) -> bool:
    """Whether a script sets a 5 s+ `setTimeout`, or a shell command runs `sleep <n>`."""
    if name == EXECUTE_TYPESCRIPT:
        field, pattern = "code", LONG_TIMEOUT_PATTERN
    elif name.endswith(SHELL_SUFFIX):
        field, pattern = "command", SLEEP_COMMAND_PATTERN
    else:
        return False
    try:
        parsed = json.loads(arguments)
    except ValueError:
        return False
    text = parsed.get(field) if isinstance(parsed, dict) else None
    return isinstance(text, str) and pattern.search(text) is not None


@dataclass(frozen=True)
class NoWaitHook(ToolHook):
    """Refuses a script or shell call that waits, for the orchestrator's own turns only."""

    async def refusal_reason(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        return NO_WAIT_REFUSAL if is_waiting_call(sig.name, sig.args) else None

    async def post_call_note(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        return None
