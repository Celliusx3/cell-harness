"""The append-only log, and the session that owns one."""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import ToolReference
from harness.session.models import (
    AssistantMessageEvent,
    SessionEvent,
    SessionHeader,
    ToolResultEvent,
    TurnStart,
)


class Session:
    """One agent interaction: an append-only event log plus its header."""

    def __init__(self, header: SessionHeader, events: Sequence[SessionEvent] = ()) -> None:
        self.header = header
        self._events: list[SessionEvent] = list(events)

    @property
    def id(self) -> str:
        """The session's identity, read from the header."""
        return self.header.id

    def append(self, event: SessionEvent) -> int:
        """Record one event."""
        self._events.append(event)
        return len(self._events) - 1

    def events(self) -> Sequence[SessionEvent]:
        """Every event, oldest first."""
        return self._events

    def next_turn(self) -> int:
        """The index the next turn should open with."""
        return sum(1 for event in self._events if isinstance(event, TurnStart))

    def tools_selected(self) -> tuple[str, ...]:
        """The tools this conversation has selected, oldest first, no repeats."""
        order: dict[str, None] = {}
        for event in self._events:
            if isinstance(event, ToolResultEvent):
                for block in event.message.content:
                    if isinstance(block, ToolReference):
                        order.pop(block.tool_name, None)
                        order[block.tool_name] = None
        return tuple(order)

    def context_size(self) -> int | None:
        """Input plus output tokens of the last reply that reported usage, or `None`."""
        for event in reversed(self._events):
            if isinstance(event, AssistantMessageEvent) and event.usage is not None:
                return event.usage.input_tokens + event.usage.output_tokens
        return None
