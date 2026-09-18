"""One turn's steps: ask the model, run what it asked for, repeat.

Split from `loop.py` at the length cap, along the seam that was already
there: `LoopAgent` says how a turn *opens* — with a user message, or with the
result of a call the person answered — and this module drives it from there
to its end. Every step is one model request plus the tools it asked for; a
step that ends without tool calls ends the turn.

A tool whose outcome is `Pending` ends the turn too, with **no result** for
that call: the person answers it, in a later turn. That turn's `turn/end`
says `pending`, which is how `repair` knows the open call is deliberate.

A turn cut short — the tab closed, the stop button, a bug — still leaves a
log a provider accepts. Each phase repairs what only it knows about, on its
way out: `_stream_reply` the text on screen with no message yet, `_run_tool_calls` the
calls with no result yet, `drive` the missing `turn/end`.
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from harness.agent.events import (
    AgentCompleted,
    AgentFailed,
    AgentPending,
    ToolPending,
    ToolProgress,
    ToolResult,
)
from harness.agent.tool_run import tool_events
from harness.llm.messages import ApplicationMessage, AssistantMessage, ToolCall, ToolMessage
from harness.llm.stream import CONTEXT_WINDOW_EXCEEDED, Completed, Failed, TextChunk, ToolCallChunk
from harness.session.compaction import CompactionEnd, CompactionPrune
from harness.session.log import Session
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantChunk,
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnEndReason,
)
from harness.session.repair import REPAIRED, TOOL_OUTCOME_UNKNOWN

if TYPE_CHECKING:
    from harness.agent.loop import LoopAgent

# An adapter owes exactly one terminal event; a missing one is a failure, not a quirk.
NO_TERMINAL = "stream ended without a terminal event"

# A provider requires one result per call, so an abandoned turn must answer every
# call it dispatched. Same words as a crash repair: the outcome is unknown either way.
INTERRUPTED_RESULT = TOOL_OUTCOME_UNKNOWN

TurnEvent = (
    TextChunk
    | ToolCallChunk
    | ToolProgress
    | ToolResult
    | ToolPending
    | AgentCompleted
    | AgentPending
    | AgentFailed
)


@dataclass(frozen=True)
class RetryStep:
    """The provider refused the request for its size and the history has been
    shrunk: run the same step again."""


async def drive(agent: LoopAgent, session: Session, turn: int) -> AsyncIterator[TurnEvent]:
    """From an opened turn to its end: the reply's chunks live, tool progress
    and results as they settle, then exactly one terminal."""
    step = 0
    answer = ""  # text across steps, so a tool-calling step's preamble survives
    outcome: AgentCompleted | AgentPending | AgentFailed

    try:
        # No step cap: repeated failures are a hook's to refuse, and the
        # user's stop button bounds the rest. dsh has none either.
        for step in itertools.count():
            session.append(StepStart(turn=turn, step=step))

            # Before the request is built: shrink the history if it has grown
            # past the window. Appends events a fold reads back, so the
            # request built below already sees the compacted view.
            if agent.compaction is not None:
                await _consume(agent.compaction.before_step(session, turn=turn))

            reply: Completed | Failed | RetryStep | None = None
            async with aclosing(_stream_reply(agent, session, turn=turn, step=step)) as chunks:
                async for event in chunks:
                    if isinstance(event, (TextChunk, ToolCallChunk)):
                        yield event
                    else:
                        reply = event
            assert reply is not None  # `_stream_reply` ends with a terminal or raises

            if isinstance(reply, RetryStep):
                continue
            if isinstance(reply, Failed):
                _close(session, turn, step, "failed")
                outcome = AgentFailed(reason=reply.reason)
                break

            answer += reply.full_text
            if not reply.tool_calls:
                _close(session, turn, step, "completed")
                outcome = AgentCompleted(text=answer)
                break

            pending: ToolPending | None = None
            async with aclosing(
                _run_tool_calls(agent, reply.tool_calls, session=session, turn=turn, step=step)
            ) as results:
                async for event in results:
                    if isinstance(event, ToolPending):
                        pending = event
                    yield event
            if pending is not None:
                _close(session, turn, step, "pending")
                outcome = AgentPending(tool_call_id=pending.tool_call_id, name=pending.name)
                break
            session.append(StepEnd(turn=turn, step=step))
    except BaseException:
        # GeneratorExit and CancelledError alike, which no `except Exception`
        # would. Nothing is awaited: `append` is synchronous.
        _close(session, turn, step, "cancelled")
        raise
    yield outcome


async def _stream_reply(
    agent: LoopAgent, session: Session, *, turn: int, step: int
) -> AsyncIterator[TextChunk | ToolCallChunk | Completed | Failed | RetryStep]:
    """One model request: the reply's chunks live, logged as they stream, then
    exactly one terminal — a `Completed` with its message logged, a `Failed`,
    or `RetryStep`."""
    # Read per step, so a tool that appeared mid-turn is offered now.
    specs = agent.tools.specs(session.tools_selected()) if agent.tools else None
    messages = agent.request_messages(session)
    if agent.checkpoint is not None:
        await agent.checkpoint(session)

    completed: Completed | None = None
    failed: Failed | None = None
    partial = ""
    try:
        # `aclosing`: closing this generator mid-stream must close the
        # adapter's too, or its HTTP response outlives the turn.
        async with aclosing(
            agent.client.stream_completion(messages, agent.model, tools=specs)
        ) as stream:
            async for event in stream:
                session.append(AssistantChunk(turn=turn, step=step, chunk=event))
                if isinstance(event, TextChunk):
                    partial += event.text
                    yield event
                elif isinstance(event, ToolCallChunk):
                    yield event
                elif isinstance(event, Completed):
                    completed = event
                elif isinstance(event, Failed):
                    failed = event

        if failed is not None or completed is None:
            # `_reduced` bounds the retries: a history that cannot shrink
            # further fails the turn instead.
            if (
                failed is not None
                and failed.code == CONTEXT_WINDOW_EXCEEDED
                and agent.compaction is not None
                and _reduced(await _consume(agent.compaction.recover(session, turn=turn)))
            ):
                yield RetryStep()
                return
            yield failed if failed is not None else Failed(reason=NO_TERMINAL)
            return

        session.append(
            AssistantMessageEvent(
                turn=turn,
                step=step,
                message=AssistantMessage(
                    content=completed.full_text, tool_calls=completed.tool_calls
                ),
                usage=completed.usage,
            )
        )
        yield completed
    except BaseException:
        # Cut short with text on screen, mid-stream or mid-recovery: log it, so
        # the next request matches what the person saw. `except`, not `finally`:
        # a refusal that ends the turn keeps the chunks and logs no message.
        if partial:
            session.append(
                AssistantMessageEvent(
                    turn=turn,
                    step=step,
                    message=AssistantMessage(content=partial),
                    interrupted=True,
                )
            )
        raise


async def _run_tool_calls(
    agent: LoopAgent, calls: tuple[ToolCall, ...], *, session: Session, turn: int, step: int
) -> AsyncIterator[ToolProgress | ToolResult | ToolPending]:
    """A step's calls, in order: each one's events as it settles, then what
    the hooks wanted the model told. A call still unanswered when this is cut
    off gets a result anyway: a provider requires one per call it was shown."""
    owed = list(calls)
    # Logged after the calls, not between: a provider wants the `tool`
    # messages directly behind the `assistant` that asked.
    notes: list[str] = []
    try:
        for call in calls:
            # `tool/call` is logged and made durable *before* the tool runs,
            # so a crash mid-side-effect is recoverable as "may have
            # happened" rather than "never started".
            session.append(ToolCallEvent(turn=turn, step=step, call=call))
            if agent.checkpoint is not None:
                await agent.checkpoint(session)
            async with aclosing(
                tool_events(agent, call, session=session, turn=turn, step=step, notes=notes)
            ) as events:
                async for event in events:
                    if isinstance(event, (ToolResult, ToolPending)):
                        owed.remove(call)
                    yield event
        if notes:
            session.append(
                ApplicationMessageEvent(
                    turn=turn, message=ApplicationMessage(content="\n\n".join(notes))
                )
            )
    finally:
        # Nothing is awaited: a cancelled turn is fully written by the time
        # it unwinds.
        for call in owed:
            session.append(
                ToolResultEvent(
                    turn=turn,
                    step=step,
                    message=ToolMessage(tool_call_id=call.id, content=INTERRUPTED_RESULT),
                    error=REPAIRED,
                )
            )


async def _consume(events: AsyncIterator[object]) -> list[object]:
    """Drain a compaction generator, closing it if the turn is cancelled
    mid-summary — its `finally` then closes the bracket."""
    produced: list[object] = []
    async with aclosing(events) as stream:
        async for event in stream:
            produced.append(event)
    return produced


def _reduced(produced: list[object]) -> bool:
    """Did a recovery actually shrink the history? A prune clears results; a
    summary that landed a message moves the boundary. A failed or empty
    attempt did neither, so the turn must not retry on it."""
    for event in produced:
        if isinstance(event, CompactionPrune):
            return True
        if isinstance(event, CompactionEnd) and event.succeeded:
            return True
    return False


def _close(session: Session, turn: int, step: int, reason: TurnEndReason) -> None:
    session.append(StepEnd(turn=turn, step=step))
    session.append(TurnEnd(turn=turn, reason=reason))
