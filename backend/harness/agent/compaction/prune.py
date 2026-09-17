"""Which tool results to clear before anything is summarized.

Tool results are the bulk of a long conversation and the least worth
re-reading — a transcript the model already extracted places from, a JSON blob
it already answered from. Clearing them costs no model call and loses little,
so it is tried first; the next step's real `usage` says whether it was enough.

Everything after the boundary is a candidate except a `skill` body, a result
already cleared, and the most recent `PRUNE_KEEP` — the ones the model is
likely still working from (Claude Code's microcompact keeps its recent few).
"""

from __future__ import annotations

from collections.abc import Sequence

from harness.session.compaction import pruned_ids, tail_start
from harness.session.models import SessionEvent, ToolCallEvent, ToolResultEvent
from harness.skills import SKILL

PRUNE_KEEP = 3


def prunable(events: Sequence[SessionEvent], *, keep: int = PRUNE_KEEP) -> tuple[str, ...]:
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
    return tuple(candidates[:-keep]) if len(candidates) > keep else ()
