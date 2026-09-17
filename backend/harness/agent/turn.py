"""One turn's steps: ask the model, run what it asked for, repeat.

Split from `loop.py` at the length cap, along the seam that was already
there: `LoopAgent` says how a turn *opens* — with a user message, or with the
result of a call the person answered — and this module drives it from there
to its end. Every step is one model request plus the tools it asked for; a
step that ends without tool calls ends the turn.

A tool whose outcome is `Pending` ends the turn too, with **no result** for
that call: the person answers it, in a later turn. That turn's `turn/end`
says `pending`, which is how `repair` knows the open call is deliberate.
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterator
from contextlib import aclosing
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


async def drive(agent: LoopAgent, session: Session, turn: int) -> AsyncIterator[TurnEvent]:
    """From an opened turn to its end: the reply's chunks live, tool progress
    and results as they settle, then exactly one terminal."""
    partial = ""  # streamed text not yet logged; rescued by the `finally`
    owed: list[ToolCall] = []  # dispatched calls with no result yet
    closed = False  # whether `turn/end` is already written
    step = 0
    answer = ""  # text across steps, so a tool-calling step's preamble survives

    try:
        # No step cap: repeated failures are a hook's to refuse, and the
        # user's stop button bounds the rest. dsh has none either.
        for step in itertools.count():
            session.append(StepStart(turn=turn, step=step))
            partial = ""
            owed = []

            # Before the request is built: shrink the history if it has grown
            # past the window. Appends events a fold reads back, so the
            # `request_messages` below already sees the compacted view.
            if agent.compaction is not None:
                await _consume(agent.compaction.before_step(session, turn=turn))

            # Read per step, so a tool that appeared mid-turn is offered now.
            specs = agent.tools.specs(session.tools_selected()) if agent.tools else None
            messages = agent.request_messages(session)
            if agent.checkpoint is not None:
                await agent.checkpoint(session)

            completed: Completed | None = None
            failed: Failed | None = None
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
                # The provider refused the request for its size: compact and
                # retry the step. Bounded — each recovery shrinks the derived
                # history, and a log that is only a summary has nothing left,
                # so a summary that cannot shrink further fails the turn here.
                if (
                    failed is not None
                    and failed.code == CONTEXT_WINDOW_EXCEEDED
                    and agent.compaction is not None
                    and _reduced(await _consume(agent.compaction.recover(session, turn=turn)))
                ):
                    continue
                _close(session, turn, step, "failed")
                closed = True
                yield AgentFailed(reason=failed.reason if failed else NO_TERMINAL)
                return

            answer += completed.full_text
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
            partial = ""  # logged now; the `finally` must not log it again

            if not completed.tool_calls:
                _close(session, turn, step, "completed")
                closed = True
                yield AgentCompleted(text=answer)
                return

            owed = list(completed.tool_calls)
            # What the hooks said about this step's calls. Logged after them,
            # not between: a provider wants the `tool` messages directly
            # behind the `assistant` that asked.
            notes: list[str] = []
            # The call the person must answer, if this step had one. The
            # step's other calls still run and log their results first.
            pending: ToolPending | None = None
            for call in completed.tool_calls:
                # `tool/call` is logged and made durable *before* the tool
                # runs, so a crash mid-side-effect is recoverable as "may have
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
                        if isinstance(event, ToolPending):
                            pending = event
                        yield event

            if notes:
                session.append(
                    ApplicationMessageEvent(
                        turn=turn, message=ApplicationMessage(content="\n\n".join(notes))
                    )
                )
            if pending is not None:
                _close(session, turn, step, "pending")
                closed = True
                yield AgentPending(tool_call_id=pending.tool_call_id, name=pending.name)
                return
            session.append(StepEnd(turn=turn, step=step))
    finally:
        # Runs on GeneratorExit and CancelledError alike, which no `except
        # Exception` would. Nothing is awaited: `append` is synchronous.
        if not closed:
            if partial:
                session.append(
                    AssistantMessageEvent(
                        turn=turn,
                        step=step,
                        message=AssistantMessage(content=partial),
                        interrupted=True,
                    )
                )
            for call in owed:
                session.append(
                    ToolResultEvent(
                        turn=turn,
                        step=step,
                        message=ToolMessage(tool_call_id=call.id, content=INTERRUPTED_RESULT),
                        error=REPAIRED,
                    )
                )
            _close(session, turn, step, "cancelled")


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
