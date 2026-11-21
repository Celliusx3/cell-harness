"""What a running tool is handed about its call."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from harness.tools.domain.decision import ApprovalMode


class ToolProgressReporter(Protocol):
    """What a tool calls to say how far along it is."""

    def __call__(self, *, percent: float | None, message: str | None) -> Awaitable[None]: ...


@dataclass(frozen=True)
class CallOrigin:
    """Who a call comes from: bot, conversation, mode, workspaces, and its model history."""

    bot_id: str
    conversation_id: str
    mode: ApprovalMode
    workspace: Path | None
    own_workspace: Path | None
    history_id: str


@dataclass(frozen=True)
class ToolContext:
    """Per-call facts, read-only, given to every `execute`."""

    call_id: str
    progress: ToolProgressReporter
    origin: CallOrigin
