"""Answering tool calls a dead process never got back to.

The loop's `finally` handles a turn that was *gracefully* abandoned — a closed
generator, a cancelled task. `kill -9` runs no `finally`, so a log can end with
an assistant message that asked for a tool and no result for it.

That log is not merely untidy. A provider **rejects** a history whose assistant
message requests a call with no matching tool message, so the resumed session
would fail on its first request. Writing the missing result is what makes resume
work at all.

**Only the missing results.** An unclosed `turn/start` or `step/start` is left
exactly as the crash left it: `derive_messages` ignores turn and step boundaries,
so closing them changes nothing the model sees, and nothing else reads them.
DeepSeek Harness does synthesize those closers and marks the turn with a
`TurnEndReason` no loop emits — worth copying the day something displays "this
conversation was interrupted", and not before.

**Nothing is ever rewritten.** The results are appended like any other events, so
the file stays append-only and the repair is itself durable.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import ToolMessage
from harness.session.models import AssistantMessageEvent, SessionEvent, ToolResultEvent

# The model reads this, so it is written for the model rather than a maintainer.
# Deliberately *not* "this never ran": the tool was dispatched before the process
# died and may well have finished, so the honest answer is that we do not know.
TOOL_OUTCOME_UNKNOWN = (
    "error: this tool call was interrupted and its outcome is unknown. It may have "
    "completed. Retry only read-only or idempotent work; otherwise verify whether "
    "it took effect, or ask the user."
)

# Marks a result this module invented rather than a tool returned, so telemetry
# can tell a crash from a bad argument.
REPAIRED = "INTERRUPTED_BY_CRASH"


def repair(events: Sequence[SessionEvent]) -> list[SessionEvent]:
    """Results for every call the log left unanswered.

    Idempotent: a log with nothing outstanding yields nothing, so resuming twice
    does not stack results. That doubles as the "does this need repair?"
    question, which is why there is no separate predicate.
    """
    answered = {e.message.tool_call_id for e in events if isinstance(e, ToolResultEvent)}
    return [
        ToolResultEvent(
            turn=event.turn,
            step=event.step,
            message=ToolMessage(tool_call_id=call.id, content=TOOL_OUTCOME_UNKNOWN),
            error=REPAIRED,
        )
        for event in events
        if isinstance(event, AssistantMessageEvent)
        for call in event.message.tool_calls
        if call.id not in answered
    ]
