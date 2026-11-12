"""How a schedule change logged at any moment is placed in the model's history, and worded."""

from __future__ import annotations

import json
from collections.abc import Sequence

from harness.llm import UserMessage
from harness.prompts import SCHEDULE_CHANGE
from harness.session.models import (
    AssistantMessageEvent,
    ScheduleChangeEvent,
    SessionEvent,
    ToolResultEvent,
)


def after_owed_results(log: Sequence[SessionEvent]) -> tuple[SessionEvent, ...]:
    """`log` with each schedule change moved past the tool results still owed when it was logged."""
    owed: frozenset[str] = frozenset()
    held: tuple[ScheduleChangeEvent, ...] = ()
    placed: list[SessionEvent] = []
    for event in log:
        if isinstance(event, ScheduleChangeEvent) and owed:
            held = (*held, event)
            continue
        placed.append(event)
        owed = _owed_after(owed, event)
        if not owed and held:
            placed.extend(held)
            held = ()
    return (*placed, *held)


def change_message(event: ScheduleChangeEvent) -> UserMessage:
    """The change as the bot is told it."""
    change = event.change
    return UserMessage(
        content=SCHEDULE_CHANGE.format(
            change=change.change,
            schedule_id_json=json.dumps(change.schedule_id, ensure_ascii=False),
            schedule_title_json=json.dumps(change.title, ensure_ascii=False),
        )
    )


def _owed_after(owed: frozenset[str], event: SessionEvent) -> frozenset[str]:
    """The tool calls still waiting for a result once `event` is in the history."""
    if isinstance(event, AssistantMessageEvent):
        return owed | {call.id for call in event.message.tool_calls}
    if isinstance(event, ToolResultEvent):
        return owed - {event.message.tool_call_id}
    return owed
