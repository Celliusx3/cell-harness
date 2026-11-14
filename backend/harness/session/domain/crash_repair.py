"""Answering tool calls a dead process never got back to."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from harness.llm import ToolCall, ToolMessage
from harness.prompts import TOOL_OUTCOME_UNKNOWN
from harness.session.domain.compaction import CompactionEnd, unended_start
from harness.session.domain.models import (
    AssistantMessageEvent,
    SessionEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
)

INTERRUPTED_BY_CRASH = "INTERRUPTED_BY_CRASH"


class UnansweredCall(NamedTuple):
    asked: AssistantMessageEvent
    call: ToolCall


def unanswered(events: Sequence[SessionEvent]) -> list[UnansweredCall]:
    """Every call in the log with no result, with the message that made it."""
    answered = {e.message.tool_call_id for e in events if isinstance(e, ToolResultEvent)}
    return [
        UnansweredCall(event, call)
        for event in events
        if isinstance(event, AssistantMessageEvent)
        for call in event.message.tool_calls
        if call.id not in answered
    ]


def unknown_result(call_id: str, *, turn: int, step: int) -> ToolResultEvent:
    """The result for a call whose outcome was lost."""
    return ToolResultEvent(
        turn=turn,
        step=step,
        message=ToolMessage(tool_call_id=call_id, content=TOOL_OUTCOME_UNKNOWN),
        error=INTERRUPTED_BY_CRASH,
    )


def crash_repairs(events: Sequence[SessionEvent]) -> list[SessionEvent]:
    """Results for every call the log left unanswered *by accident*."""
    additions: list[SessionEvent] = []
    if not _is_waiting_on_person(events):
        additions.extend(
            unknown_result(call.id, turn=event.turn, step=event.step)
            for event, call in unanswered(events)
        )
    started = unended_start(events)
    if started is not None:
        additions.append(CompactionEnd(turn=started.turn, error=INTERRUPTED_BY_CRASH))
    return additions


def _is_waiting_on_person(events: Sequence[SessionEvent]) -> bool:
    """Did the last turn end `pending` — is the log waiting on the person, not on a dead process?"""
    turns = [e.turn for e in events if isinstance(e, TurnStart)]
    if not turns:
        return False
    last = turns[-1]
    return any(isinstance(e, TurnEnd) and e.turn == last and e.reason == "pending" for e in events)
