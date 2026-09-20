"""One turn's steps: ask the model, run what it asked for, repeat."""

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
from harness.agent.hooks import GiveUp, Tell
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

NO_TERMINAL = "stream ended without a terminal event"

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
    """The history was shrunk after a size refusal: run the same step again."""


async def drive(agent: LoopAgent, session: Session, turn: int) -> AsyncIterator[TurnEvent]:
    """From an opened turn to its end: its events as they happen, then exactly one terminal."""
    step = 0
    answer = ""
    outcome: AgentCompleted | AgentPending | AgentFailed

    try:
        for step in itertools.count():
            session.append(StepStart(turn=turn, step=step))

            if agent.compaction is not None and agent.compaction.due(session):
                await _consume(agent.compaction.reduce(session, turn=turn, trigger="auto"))

            reply: Completed | Failed | RetryStep | None = None
            async with aclosing(_stream_reply(agent, session, turn=turn, step=step)) as chunks:
                async for event in chunks:
                    if isinstance(event, (TextChunk, ToolCallChunk)):
                        yield event
                    else:
                        reply = event
            assert reply is not None

            if isinstance(reply, RetryStep):
                continue
            if isinstance(reply, Failed):
                _close(session, turn, step, "failed")
                outcome = AgentFailed(reason=reply.reason)
                break

            answer += reply.full_text
            if not reply.tool_calls:
                decision = await agent.hooks.end_of_step(session=session)
                if isinstance(decision, GiveUp):
                    _close(session, turn, step, "failed")
                    outcome = AgentFailed(reason=decision.reason)
                    break
                if isinstance(decision, Tell):
                    _tell(session, turn, step, decision.note)
                    continue
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
        _close(session, turn, step, "cancelled")
        raise
    yield outcome


async def _stream_reply(
    agent: LoopAgent, session: Session, *, turn: int, step: int
) -> AsyncIterator[TextChunk | ToolCallChunk | Completed | Failed | RetryStep]:
    """One model request: its chunks as they stream, then `Completed`, `Failed` or `RetryStep`."""
    specs = agent.tools.specs(session.tools_selected()) if agent.tools else None
    messages = agent.request_messages(session)
    if agent.checkpoint is not None:
        await agent.checkpoint(session)

    completed: Completed | None = None
    failed: Failed | None = None
    partial = ""
    try:
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
            if (
                failed is not None
                and failed.code == CONTEXT_WINDOW_EXCEEDED
                and agent.compaction is not None
                and _reduced(
                    await _consume(agent.compaction.reduce(session, turn=turn, trigger="overflow"))
                )
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
    """A step's calls in order, then what the hooks wanted the model told."""
    owed = list(calls)
    # Providers want the `tool` messages directly behind the `assistant` that asked.
    notes: list[str] = []
    try:
        for call in calls:
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
    """Drain a compaction generator, closing it if the turn is cancelled mid-summary."""
    produced: list[object] = []
    async with aclosing(events) as stream:
        async for event in stream:
            produced.append(event)
    return produced


def _reduced(produced: list[object]) -> bool:
    """Did a recovery actually shrink the history?"""
    for event in produced:
        if isinstance(event, CompactionPrune):
            return True
        if isinstance(event, CompactionEnd) and event.succeeded:
            return True
    return False


def _tell(session: Session, turn: int, step: int, note: str) -> None:
    """Close the step with a note the model reads before the next request."""
    session.append(ApplicationMessageEvent(turn=turn, message=ApplicationMessage(content=note)))
    session.append(StepEnd(turn=turn, step=step))


def _close(session: Session, turn: int, step: int, reason: TurnEndReason) -> None:
    session.append(StepEnd(turn=turn, step=step))
    session.append(TurnEnd(turn=turn, reason=reason))
