"""Project model history from the log."""

from __future__ import annotations

from collections.abc import Iterable

from harness.llm.messages import Message, ToolMessage, UserMessage
from harness.session.compaction import PRUNED, boundary, pruned_ids
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantMessageEvent,
    SessionEvent,
    ToolResultEvent,
    UserMessageEvent,
)


def derive_messages(events: Iterable[SessionEvent]) -> list[Message]:
    """The conversation as the model should see it."""
    log = tuple(events)
    pruned = pruned_ids(log)
    messages: list[Message] = []
    start = boundary(log)
    if start is not None:
        summary = log[start]
        assert summary.message is not None
        messages.append(UserMessage(content=summary.message.content))
        log = log[start + 1 :]
    for event in log:
        if isinstance(event, UserMessageEvent):
            messages.append(event.message)
        elif isinstance(event, ApplicationMessageEvent):
            messages.append(UserMessage(content=event.message.content))
        elif isinstance(event, AssistantMessageEvent):
            messages.append(event.message)
        elif isinstance(event, ToolResultEvent):
            if event.message.tool_call_id in pruned:
                messages.append(
                    ToolMessage(tool_call_id=event.message.tool_call_id, content=PRUNED)
                )
            else:
                messages.append(event.message)
    return messages
