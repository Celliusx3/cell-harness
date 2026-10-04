"""Which calls a client may answer — read off the log, never the registry."""

from __future__ import annotations

from dataclasses import dataclass

from harness.session.log import Session
from harness.session.models import SessionEvent, ToolCallEvent, ToolResultEvent


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


def pending_tool_calls(
    calls: tuple[PendingCall, ...], event: SessionEvent
) -> tuple[PendingCall, ...]:
    """The calls still unanswered once `event` has landed."""
    if isinstance(event, ToolCallEvent):
        return (*calls, PendingCall(event.call.name, event.call.id, event.call.arguments))
    if isinstance(event, ToolResultEvent):
        return tuple(call for call in calls if call.call_id != event.message.tool_call_id)
    return calls
