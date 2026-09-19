"""Which skills a conversation has loaded, so a summary can carry them across."""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import render_text
from harness.session.models import SessionEvent, ToolCallEvent, ToolResultEvent, UserMessageEvent
from harness.skills import SKILL
from harness.skills.invocation import MARKER, display

_TAG = MARKER.lstrip()


def _name(body: str) -> str | None:
    """The name in a skill body's opening tag, or `None` for text that is not one."""
    if not body.startswith(_TAG):
        return None
    name, quote, _ = body[len(_TAG) :].partition('"')
    return name if quote else None


def retained_skills(events: Sequence[SessionEvent]) -> tuple[tuple[str, str], ...]:
    """`(name, body)` per skill loaded so far, last body per name, in load order."""
    calls: dict[str, str] = {}
    bodies: dict[str, str] = {}
    for event in events:
        if isinstance(event, ToolCallEvent):
            calls[event.call.id] = event.call.name
        elif isinstance(event, ToolResultEvent) and calls.get(event.message.tool_call_id) == SKILL:
            body = render_text(event.message.content)
            if (name := _name(body)) is not None:
                bodies[name] = body
        elif isinstance(event, UserMessageEvent):
            shown = display(event.message.content)
            if shown is not None:
                _, _, rest = event.message.content.partition(MARKER)
                bodies[shown.skill] = _TAG + rest
    return tuple(bodies.items())
