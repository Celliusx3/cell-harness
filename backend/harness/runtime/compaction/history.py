"""What compaction asks of the events: what to clear, whether to summarize, what skills to carry."""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import render_text
from harness.session.compaction import pruned_ids, tail_start
from harness.session.models import SessionEvent, ToolCallEvent, ToolResultEvent, UserMessageEvent
from harness.skills import SKILL
from harness.skills.invocation import MARKER, display

PRUNE_KEEP = 3

_TAG = MARKER.lstrip()


def prunable_ids(events: Sequence[SessionEvent]) -> tuple[str, ...]:
    """The call ids whose results a prune would clear now, oldest first."""
    pruned = pruned_ids(events)
    names = {e.call.id: e.call.name for e in events if isinstance(e, ToolCallEvent)}
    candidates = [
        e.message.tool_call_id
        for e in events[tail_start(events) :]
        if isinstance(e, ToolResultEvent)
        and names.get(e.message.tool_call_id) != SKILL
        and e.message.tool_call_id not in pruned
    ]
    return tuple(candidates[:-PRUNE_KEEP])


def summarizable(events: Sequence[SessionEvent]) -> bool:
    """Does the un-compacted tail hold a user message to summarize?"""
    return any(e.type == "user/message" for e in events[tail_start(events) :])


def loaded_skills(events: Sequence[SessionEvent]) -> tuple[str, ...]:
    """The body of each skill loaded so far, the last per name, in load order."""
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
    return tuple(bodies.values())


def _name(body: str) -> str | None:
    """The name in a skill body's opening tag, or `None` for text that is not one."""
    if not body.startswith(_TAG):
        return None
    name, quote, _ = body[len(_TAG) :].partition('"')
    return name if quote else None
