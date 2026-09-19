"""Answering tool calls a dead process never got back to."""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import ToolCall, ToolMessage
from harness.session.compaction import CompactionEnd, open_start
from harness.session.models import (
    AssistantMessageEvent,
    SessionEvent,
    ToolResultEvent,
    TurnEnd,
)

TOOL_OUTCOME_UNKNOWN = (
    "error: this tool call was interrupted and its outcome is unknown. It may have "
    "completed. Retry only read-only or idempotent work; otherwise verify whether "
    "it took effect, or ask the user."
)

REPAIRED = "INTERRUPTED_BY_CRASH"


def unanswered(events: Sequence[SessionEvent]) -> list[tuple[AssistantMessageEvent, ToolCall]]:
    """Every call in the log with no result, with the message that made it."""
    answered = {e.message.tool_call_id for e in events if isinstance(e, ToolResultEvent)}
    return [
        (event, call)
        for event in events
        if isinstance(event, AssistantMessageEvent)
        for call in event.message.tool_calls
        if call.id not in answered
    ]


def repair(events: Sequence[SessionEvent]) -> list[SessionEvent]:
    """Results for every call the log left unanswered *by accident*."""
    pending = {e.turn for e in events if isinstance(e, TurnEnd) and e.reason == "pending"}
    additions: list[SessionEvent] = [
        ToolResultEvent(
            turn=event.turn,
            step=event.step,
            message=ToolMessage(tool_call_id=call.id, content=TOOL_OUTCOME_UNKNOWN),
            error=REPAIRED,
        )
        for event, call in unanswered(events)
        if event.turn not in pending
    ]
    started = open_start(events)
    if started is not None:
        additions.append(CompactionEnd(turn=started.turn, error=REPAIRED))
    return additions
