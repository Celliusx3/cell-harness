"""Project model history from the log.

**This is the only way model history is produced.** There is no second store, no
accumulated list, no cache. The loop calls this before every request, so what the
model sees is always exactly what the log says happened — which is what makes
resume, fork, and compaction consequences of the log rather than features that
have to be built and kept in sync.

The rule it enforces in one direction: anything the model sees must be in the
log, because nothing else reaches a request. The invariant that enforces it in
the other direction — that nothing in a request is *missing* from the log —
arrives in phase 3, when resume makes it testable.

Compaction is honoured here and only here. The last successful
`compaction/end` is a boundary: derivation starts there, with its message in
the user role, and nothing before it reaches the model. A result named by a
`compaction/prune` renders as a placeholder. The log keeps every original
event either way — phase 11's "appends, never rewrites".

Chunks are skipped. They exist for replay fidelity, and the assembled
`assistant/message` beside them is what the model is shown; including both would
send the reply twice. `tool/call` is skipped for the same reason — the calls
already ride on the assistant message that requested them.

The one invariant with teeth here: a provider requires **exactly one** tool
message per tool call in the preceding assistant message. A history missing one
is not merely incomplete, it is rejected outright — so the loop must write a
result on every path, including when a turn is abandoned mid-call.

Nothing here *checks* that invariant. The loop knows what it owes because it
tracks the calls it dispatched, and a check derived from the history would be a
second answer to a question that already has one. When phase 3 loads a log it did
not build, that changes — and the check belongs with `resume`, not here.
"""

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
    """The conversation as the model should see it.

    No system message: the loop prepends one per request so it can reflect the
    agent running *this* turn. Turn and step boundaries are structure, not
    content, and are dropped here.
    """
    log = tuple(events)
    pruned = pruned_ids(log)
    messages: list[Message] = []
    start = boundary(log)
    if start is not None:
        # The summary stands in for everything before it. User role, like an
        # `application/message`: the harness's words, where Claude Code puts
        # its continuation summary too.
        summary = log[start]
        assert summary.message is not None  # `boundary` only returns one with a message
        messages.append(UserMessage(content=summary.message.content))
        log = log[start + 1 :]
    for event in log:
        if isinstance(event, UserMessageEvent):
            messages.append(event.message)
        elif isinstance(event, ApplicationMessageEvent):
            # User role on the wire: no provider has another, and the user turn
            # is where Claude Code puts its reminders too.
            messages.append(UserMessage(content=event.message.content))
        elif isinstance(event, AssistantMessageEvent):
            # An interrupted reply stays in history. The model said it and the
            # user read it, so hiding it would make the next turn's context
            # disagree with what is on screen.
            messages.append(event.message)
        elif isinstance(event, ToolResultEvent):
            if event.message.tool_call_id in pruned:
                messages.append(
                    ToolMessage(tool_call_id=event.message.tool_call_id, content=PRUNED)
                )
            else:
                messages.append(event.message)
    return messages
