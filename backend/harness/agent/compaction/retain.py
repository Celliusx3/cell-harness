"""Which skills a conversation has loaded, so a summary can carry them across.

A loaded skill is behavioural guidance, not data: losing it mid-conversation
degrades the agent with no visible error (the Agent Skills spec's compaction
rule). Two shapes put a body in the log — the `skill` tool's result, and a
`/name` message the gateway expanded in place — and both open with the same
tag, so one fold finds them. The last body per name wins: a skill edited and
reloaded is re-attached as last read.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import render_text
from harness.session.models import SessionEvent, ToolCallEvent, ToolResultEvent, UserMessageEvent
from harness.skills import SKILL
from harness.skills.invocation import MARKER, display

_TAG = MARKER.lstrip()  # `<skill name="`


def _name(body: str) -> str | None:
    """The name in a body's opening tag, or `None` for text that is not one —
    a `skill` call with `path` answers `<skill_file …>`, not a body."""
    if not body.startswith(_TAG):
        return None
    name, quote, _ = body[len(_TAG) :].partition('"')
    return name if quote else None


def retained_skills(events: Sequence[SessionEvent]) -> tuple[tuple[str, str], ...]:
    """`(name, body)` for every skill loaded so far, last body per name, in
    the order first loaded."""
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
