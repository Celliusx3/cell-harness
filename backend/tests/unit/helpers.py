"""Assertions shared across test modules.

`unanswered_calls` lives here rather than in `harness/` because nothing in the
product calls it: the loop knows what it owes from the calls it dispatched, so a
check derived from history would be a second answer to a settled question. It is
how *tests* prove the loop's repair path worked.

When phase 3 loads a log it did not build, a real runtime check earns its place —
and belongs with `resume`, which is the code that would act on it.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import AssistantMessage, Message, ToolMessage


def unanswered_calls(messages: Sequence[Message]) -> list[str]:
    """Tool call ids with no matching tool message.

    Empty when the history is one a provider will accept. Non-empty means a turn
    died between asking and answering, which a provider rejects outright rather
    than tolerating.

    `Sequence`, not `Iterable`: this reads `messages` twice, and a generator
    would be exhausted by the first pass — leaving the second to find no calls
    and report a broken history as fine. An assertion that fails open is worse
    than no assertion, so the type says what the body actually needs.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    return [
        call.id
        for m in messages
        if isinstance(m, AssistantMessage)
        for call in m.tool_calls
        if call.id not in answered
    ]


async def no_progress(*, percent: float | None, message: str | None) -> None:
    """A reporter that discards, for tests with nowhere to put progress.

    Lives here, not in `harness/`, because the product never needs one: the loop
    always has a real queue to report into. `ToolProgressReporter` is required
    rather than defaulted at every call site precisely so a *caller* that forgets
    one is a type error, not progress that silently never arrives.
    """
    return None
