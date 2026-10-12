"""The append-only log, and the session that owns one."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from harness.llm.messages import ToolReference
from harness.session.models import (
    ApprovalGrant,
    AssistantMessageEvent,
    BotInstructionsEvent,
    GroupMembersEvent,
    SessionEvent,
    SessionHeader,
    ToolCallEvent,
    ToolResultEvent,
    TurnStart,
)
from harness.session.speakers import last_speaker, turn_speakers


class Numbered(NamedTuple):
    """One event and its number in the chat."""

    number: int
    event: SessionEvent


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

    def numbered_events_from(self, number: int) -> list[Numbered]:
        """The events numbered `number` and up; all of them when `number` predates this file."""
        first = self.header.numbered_from
        start = max(number - first, 0)
        return [
            Numbered(first + index, event)
            for index, event in enumerate(self._events[start:], start)
        ]

    def next_number(self) -> int:
        """The number the next event will get."""
        return self.header.numbered_from + len(self._events)

    def next_turn(self) -> int:
        """The index the next turn should open with."""
        return sum(1 for event in self._events if isinstance(event, TurnStart))

    def speaker_id(self) -> str | None:
        """The bot that opened the last turn; `None` when it names none or no turn was opened."""
        return last_speaker(self._events)

    def speaker_of_call(self, call_id: str) -> str | None:
        """The bot whose turn asked for call `call_id`; `None` when that turn names none."""
        speakers = turn_speakers(self._events)
        for event in self._events:
            if isinstance(event, ToolCallEvent) and event.call.id == call_id:
                return speakers.get(event.turn)
        return None

    def tools_selected(self) -> tuple[str, ...]:
        """The tools the last turn's speaker has selected, oldest first, no repeats."""
        others = self._turns_of_others()
        order: dict[str, None] = {}
        for event in self._events:
            if isinstance(event, ToolResultEvent) and event.turn not in others:
                for block in event.message.content:
                    if isinstance(block, ToolReference):
                        order.pop(block.tool_name, None)
                        order[block.tool_name] = None
        return tuple(order)

    def tools_granted(self) -> frozenset[str]:
        """The tools the person allowed the last turn's speaker to run unasked."""
        others = self._turns_of_others()
        return frozenset(
            e.tool for e in self._events if isinstance(e, ApprovalGrant) and e.turn not in others
        )

    def bot_instructions(self, bot_id: str | None) -> BotInstructionsEvent | None:
        """The instructions logged last for `bot_id` or for no bot, compacted or not, or `None`."""
        for event in reversed(self._events):
            if isinstance(event, BotInstructionsEvent) and event.bot_id in (bot_id, None):
                return event
        return None

    def group_members(self) -> GroupMembersEvent | None:
        """The group's name and members as logged last; `None` in a bot's own chat."""
        for event in reversed(self._events):
            if isinstance(event, GroupMembersEvent):
                return event
        return None

    def context_size(self) -> int | None:
        """Input plus output tokens of the last reply that reported usage, or `None`."""
        for event in reversed(self._events):
            if isinstance(event, AssistantMessageEvent) and event.usage is not None:
                return event.usage.input_tokens + event.usage.output_tokens
        return None

    def _turns_of_others(self) -> frozenset[int]:
        """The turns a bot other than the last turn's speaker opened."""
        speaker = self.speaker_id()
        return frozenset(
            turn for turn, bot_id in turn_speakers(self._events).items() if bot_id != speaker
        )
