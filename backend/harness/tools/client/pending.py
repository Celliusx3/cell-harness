"""Which call a client may answer — read off the log, never the registry.

The log is what the client was shown, so what it may answer is decided by the
same record: the current turn's call to a client tool that has no result yet.
A call from an earlier turn already has its result — the loop writes one on
every path — and a call to any other tool is not the client's to answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness.session.log import Session
from harness.session.models import ToolCallEvent, ToolResultEvent, TurnStart


@dataclass(frozen=True)
class PendingCall:
    """One client-tool call with no result yet."""

    name: str
    call_id: str
    # The model's raw argument string, for a platform that renders the ask
    # from what was asked.
    arguments: str


def pending_call(session: Session, names: frozenset[str]) -> PendingCall | None:
    """The current turn's unanswered call to a tool in `names`, or `None`."""
    pending: PendingCall | None = None
    for event in session.events():
        if isinstance(event, TurnStart):
            pending = None
        elif isinstance(event, ToolCallEvent) and event.call.name in names:
            pending = PendingCall(event.call.name, event.call.id, event.call.arguments)
        elif (
            isinstance(event, ToolResultEvent)
            and pending is not None
            and event.message.tool_call_id == pending.call_id
        ):
            pending = None
    return pending
