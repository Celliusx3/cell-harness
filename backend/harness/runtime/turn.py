"""One turn's steps: ask the model, run what it asked for, repeat."""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from harness.llm.messages import ApplicationMessage, AssistantMessage
from harness.llm.stream import CONTEXT_WINDOW_EXCEEDED, Completed, Failed, TextChunk, ToolCallChunk
from harness.runtime.compaction import run_compaction, should_compact
from harness.runtime.events import (
    AgentCompleted,
    AgentFailed,
    AgentPending,
    ToolPending,
    TurnEvent,
)
from harness.runtime.hooks import GiveUp, Tell
from harness.runtime.tool_run import run_tool_calls
from harness.session.compaction import CompactionEnd, CompactionPrune, CompactionTrigger
from harness.session.log import Session
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantChunk,
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    TurnEnd,
    TurnEndReason,
)

if TYPE_CHECKING:
    from harness.runtime.service import Runtime

NO_TERMINAL = "stream ended without a terminal event"


@dataclass(frozen=True)
class RetryStep:
    """The history was shrunk after a size refusal: run the same step again."""


async def run_turn(runtime: Runtime, session: Session, turn: int) -> AsyncIterator[TurnEvent]:
    """From an opened turn to its end: its events as they happen, then exactly one terminal."""
    step = 0
    outcome: AgentCompleted | AgentPending | AgentFailed

    try:
        for step in itertools.count():
            session.append(StepStart(turn=turn, step=step))

            if should_compact(runtime, session):
                await _shrink_history(runtime, session, turn=turn, trigger="auto")

            reply: Completed | Failed | RetryStep | None = None
            async with aclosing(_stream_reply(runtime, session, turn=turn, step=step)) as chunks:
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

            if not reply.tool_calls:
                decision = await runtime.hooks.end_of_step(session=session)
                if isinstance(decision, GiveUp):
                    _close(session, turn, step, "failed")
                    outcome = AgentFailed(reason=decision.reason)
                    break
                if isinstance(decision, Tell):
                    _tell(session, turn, step, decision.note)
                    continue
                _close(session, turn, step, "completed")
                outcome = AgentCompleted(text=reply.full_text)
                break

            pending: ToolPending | None = None
            async with aclosing(
                run_tool_calls(runtime, reply.tool_calls, session=session, turn=turn, step=step)
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
    runtime: Runtime, session: Session, *, turn: int, step: int
) -> AsyncIterator[TextChunk | ToolCallChunk | Completed | Failed | RetryStep]:
    """One model request: its chunks as they stream, then `Completed`, `Failed` or `RetryStep`."""
    specs = runtime.tools.specs(session.tools_selected()) if runtime.tools else None
    messages = runtime.request_messages(session)
    if runtime.checkpoint is not None:
        await runtime.checkpoint(session)

    completed: Completed | None = None
    failed: Failed | None = None
    partial = ""
    try:
        async with aclosing(
            runtime.client.stream_completion(messages, runtime.model, tools=specs)
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
            failure = failed if failed is not None else Failed(reason=NO_TERMINAL)
            if failure.code == CONTEXT_WINDOW_EXCEEDED and await _shrink_history(
                runtime, session, turn=turn, trigger="overflow"
            ):
                yield RetryStep()
            else:
                yield failure
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


async def _shrink_history(
    runtime: Runtime, session: Session, *, turn: int, trigger: CompactionTrigger
) -> bool:
    """One compaction, run to its end: `True` when it pruned or wrote a summary."""
    shrank = False
    async with aclosing(run_compaction(runtime, session, turn=turn, trigger=trigger)) as events:
        async for event in events:
            if isinstance(event, CompactionPrune) or (
                isinstance(event, CompactionEnd) and event.succeeded
            ):
                shrank = True
    return shrank


def _tell(session: Session, turn: int, step: int, note: str) -> None:
    """Close the step with a note the model reads before the next request."""
    session.append(ApplicationMessageEvent(turn=turn, message=ApplicationMessage(content=note)))
    session.append(StepEnd(turn=turn, step=step))


def _close(session: Session, turn: int, step: int, reason: TurnEndReason) -> None:
    session.append(StepEnd(turn=turn, step=step))
    session.append(TurnEnd(turn=turn, reason=reason))
