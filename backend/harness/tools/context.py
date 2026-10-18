"""What a tool is handed about the call it is running."""

from __future__ import annotations

from dataclasses import dataclass

from harness.tools.progress import ToolProgressReporter


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
