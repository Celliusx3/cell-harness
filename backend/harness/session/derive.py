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

Chunks are skipped. They exist for replay fidelity, and the assembled
`assistant/message` beside them is what the model is shown; including both would
send the reply twice.
"""

from __future__ import annotations

from collections.abc import Iterable

from harness.llm.messages import Message
from harness.session.events import AssistantMessageEvent, SessionEvent, UserMessageEvent


def derive_messages(events: Iterable[SessionEvent]) -> list[Message]:
    """The conversation as the model should see it.

    No system message: the loop prepends one per request so it can reflect the
    agent running *this* turn. Turn boundaries are structure, not content, and
    are dropped here.
    """
    messages: list[Message] = []
    for event in events:
        if isinstance(event, UserMessageEvent):
            messages.append(event.message)
        elif isinstance(event, AssistantMessageEvent):
            # An interrupted reply stays in history. The model said it and the
            # user read it, so hiding it would make the next turn's context
            # disagree with what is on screen.
            messages.append(event.message)
    return messages
