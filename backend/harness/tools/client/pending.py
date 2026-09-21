"""Which calls a client may answer — read off the log, never the registry."""

from __future__ import annotations

from dataclasses import dataclass

from harness.session.log import Session
from harness.session.models import ToolCallEvent, ToolResultEvent


@dataclass(frozen=True)
class PendingCall:
    """One call the client answers, with no result yet."""

    name: str
    call_id: str
    arguments: str


def pending_calls(session: Session, names: frozenset[str]) -> tuple[PendingCall, ...]:
    """Every unanswered call to a tool in `names`, in log order."""
    answered = {
        event.message.tool_call_id
        for event in session.events()
        if isinstance(event, ToolResultEvent)
    }
    return tuple(
        PendingCall(event.call.name, event.call.id, event.call.arguments)
        for event in session.events()
        if isinstance(event, ToolCallEvent)
        and event.call.name in names
        and event.call.id not in answered
    )
