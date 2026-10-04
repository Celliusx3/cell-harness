"""Project model history from the log."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from harness.llm.messages import Block, Message, Text, ToolMessage, UserMessage
from harness.session.compaction import PRUNED, boundary, pruned_ids
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantMessageEvent,
    SessionEvent,
    ToolResultEvent,
    UserMessageEvent,
)

RESULT_LIMIT = 12_000
CUT_NOTE = (
    "\n\n[cut: this result was {total:,} characters and only the first {limit:,} are shown. "
    "If you need what was cut, ask for a smaller part, such as a narrower query or fewer rows.]"
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
                messages.append(_limited(event.message))
    return messages


def _limited(message: ToolMessage) -> ToolMessage:
    total = sum(len(block.text) for block in message.content if isinstance(block, Text))
    if total <= RESULT_LIMIT:
        return message
    note = CUT_NOTE.format(total=total, limit=RESULT_LIMIT)
    return ToolMessage(
        tool_call_id=message.tool_call_id, content=tuple(_cut_blocks(message.content, note))
    )


def _cut_blocks(blocks: tuple[Block, ...], note: str) -> Iterator[Block]:
    start = 0
    for block in blocks:
        if not isinstance(block, Text):
            yield block
            continue
        end = start + len(block.text)
        if end <= RESULT_LIMIT:
            yield block
        elif start <= RESULT_LIMIT:
            yield Text(text=block.text[: RESULT_LIMIT - start] + note)
        start = end
