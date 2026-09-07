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
from datetime import UTC, datetime

from harness.llm.messages import AssistantMessage, Message, ToolMessage
from harness.session.log import Session
from harness.session.models import SessionHeader
from harness.tools.definition import ToolDefinition
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolProvider, ToolRegistry


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


def new_session(session_id: str = "s") -> Session:
    """A session with a throwaway header, for tests that only care about the log.

    `created_at` is fixed rather than `now()` so a header that leaks into an
    assertion compares equal across runs.
    """
    return Session(SessionHeader(id=session_id, created_at=datetime(2026, 1, 1, tzinfo=UTC)))


def pipeline_for(*tools: ToolDefinition, providers: Sequence[ToolProvider] = ()) -> ToolPipeline:
    """A registry, a dispatcher and a pipeline over `tools`, offering all of them.

    The three arguments are required in the product so nobody inherits a tool
    list or a second dispatcher by accident. Tests that do not care about either
    say so once, here, rather than at every construction.
    """
    registry = ToolRegistry(tools, providers=providers)
    return ToolPipeline(registry, ToolDispatcher(registry), default_tools=())
