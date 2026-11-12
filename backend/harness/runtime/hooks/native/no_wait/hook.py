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
WAITING = re.compile(r"setTimeout\([^;]*?,\s*(?:[5-9]\d{3}|[1-9]\d{4,})\s*\)|\bsleep\b")


def waits(name: str, arguments: str) -> bool:
    """Whether a script's code, or a shell's command, waits: `sleep`, or a 5 s+ `setTimeout`."""
    if name == EXECUTE_TYPESCRIPT:
        field = "code"
    elif name.endswith(SHELL_SUFFIX):
        field = "command"
    else:
        return False
    try:
        parsed = json.loads(arguments)
    except ValueError:
        return False
    text = parsed.get(field) if isinstance(parsed, dict) else None
    return isinstance(text, str) and WAITING.search(text) is not None


@dataclass(frozen=True)
class NoWaitHook(ToolHook):
    """Refuses a script or shell call that waits, for the orchestrator's own turns only."""

    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        return NO_WAIT_REFUSAL if waits(sig.name, sig.args) else None

    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        return None
