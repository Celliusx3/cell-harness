"""What a running tool is handed about its call."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol


class ToolProgressReporter(Protocol):
    """What a tool calls to say how far along it is."""

    def __call__(self, *, percent: float | None, message: str | None) -> Awaitable[None]: ...


@dataclass(frozen=True)
class CallOrigin:
    """Who a call comes from: the bot and the conversation it is in."""

    bot_id: str
    conversation_id: str


@dataclass(frozen=True)
class ToolContext:
    """Per-call facts, read-only, given to every `execute`."""

    call_id: str
    progress: ToolProgressReporter
    origin: CallOrigin
