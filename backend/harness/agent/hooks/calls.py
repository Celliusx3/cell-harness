"""The turn so far, as a hook reads it."""

from __future__ import annotations

import json
from dataclasses import dataclass

from harness.llm.messages import ToolCall, render_text
from harness.session.log import Session
from harness.session.models import AssistantMessageEvent, ToolCallEvent, ToolResultEvent, TurnStart
from harness.tools.definition import BLOCKED


@dataclass(frozen=True)
class CompletedCall:
    """One call of this turn, joined with its result."""

    name: str
    args: str
    error: str | None
    text: str

    @property
    def failed(self) -> bool:
        return self.error is not None


@dataclass(frozen=True)
class Signature:
    """A call as a hook sees it: its tool and its normalised arguments."""

    name: str
    args: str

    @classmethod
    def of(cls, call: ToolCall) -> Signature:
        return cls(name=call.name, args=normalise(call.arguments))

    def matches(self, entry: CompletedCall) -> bool:
        return (entry.name, entry.args) == (self.name, self.args)

    def same_tool(self, entry: CompletedCall) -> bool:
        return entry.name == self.name


def normalise(arguments: str) -> str:
    """The same arguments spelled the same way, whatever the model's key order or whitespace."""
    if not arguments.strip():
        return "{}"
    try:
        return json.dumps(json.loads(arguments), sort_keys=True, separators=(",", ":"))
    except ValueError:
        return arguments


def completed_calls(session: Session) -> tuple[CompletedCall, ...]:
    """The current turn's calls that have their result, oldest first."""
    pending: dict[str, ToolCall] = {}
    completed: list[CompletedCall] = []
    for event in session.events():
        if isinstance(event, TurnStart):
            pending, completed = {}, []
        elif isinstance(event, ToolCallEvent):
            pending[event.call.id] = event.call
        elif isinstance(event, ToolResultEvent):
            call = pending.pop(event.message.tool_call_id, None)
            if call is None or event.error == BLOCKED:
                continue
            completed.append(
                CompletedCall(
                    name=call.name,
                    args=normalise(call.arguments),
                    error=event.error,
                    text=render_text(event.message.content),
                )
            )
    return tuple(completed)


def empty_replies(session: Session) -> int:
    """The current turn's trailing replies with no text and no tool call."""
    empties = 0
    for event in session.events():
        if isinstance(event, TurnStart):
            empties = 0
        elif isinstance(event, AssistantMessageEvent) and not event.interrupted:
            blank = not event.message.tool_calls and not event.message.content.strip()
            empties = empties + 1 if blank else 0
    return empties
