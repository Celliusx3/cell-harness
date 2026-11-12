"""The orchestrator waiting in its own turn for what arrives by itself."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from harness.prompts import NO_WAIT_REFUSAL
from harness.runtime.hooks.calls import CompletedCall, Signature
from harness.runtime.hooks.service import ToolHook
from harness.tools import ToolOutcome
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT

SHELL_SUFFIX = "__shell"
LONG_TIMEOUT = re.compile(r"setTimeout\([^;]*?,\s*(?:[5-9]\d{3}|[1-9]\d{4,})\s*\)")
SLEEP_COMMAND = re.compile(r"(?:^|[;&|(\n])\s*sleep\s+\d", re.MULTILINE)


def waits(name: str, arguments: str) -> bool:
    """Whether a script sets a 5 s+ `setTimeout`, or a shell command runs `sleep <n>`."""
    if name == EXECUTE_TYPESCRIPT:
        field, waiting = "code", LONG_TIMEOUT
    elif name.endswith(SHELL_SUFFIX):
        field, waiting = "command", SLEEP_COMMAND
    else:
        return False
    try:
        parsed = json.loads(arguments)
    except ValueError:
        return False
    text = parsed.get(field) if isinstance(parsed, dict) else None
    return isinstance(text, str) and waiting.search(text) is not None


@dataclass(frozen=True)
class NoWaitHook(ToolHook):
    """Refuses a script or shell call that waits, for the orchestrator's own turns only."""

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        return NO_WAIT_REFUSAL if waits(sig.name, sig.args) else None

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        return None
