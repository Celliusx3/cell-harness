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

import asyncio
import contextlib
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
from harness.llm.messages import (
    ApplicationMessage,
    AssistantMessage,
    ToolCall,
    ToolMessage,
    render_text,
)
from harness.llm.stream import Completed, Failed, TextChunk, ToolCallChunk
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
from harness.tools.definition import BLOCKED, Failure, Ok, Pending, ToolOutcome, render_outcome

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
                    _tool_events(agent, call, session=session, turn=turn, step=step, notes=notes)
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


async def _tool_events(
    agent: LoopAgent,
    call: ToolCall,
    *,
    session: Session,
    turn: int,
    step: int,
    notes: list[str],
) -> AsyncIterator[ToolProgress | ToolResult | ToolPending]:
    """One call: zero or more `ToolProgress`, then exactly one `ToolResult` —
    or a `ToolPending`, which logs nothing: the result is the person's to
    give. What a hook wants the model told goes on `notes`.

    The hooks run here, after `tool/call` was logged, so a refused call
    still has its call and result on record and the tool never starts.
    """
    refusal = await agent.hooks.pre_tool_call(call, session=session)
    outcome: ToolOutcome | None = None
    if refusal is not None:
        outcome = Failure(BLOCKED, refusal)
    else:
        async with aclosing(_run_tool(agent, call, session=session)) as events:
            async for event in events:
                if isinstance(event, ToolProgress):
                    yield event
                else:
                    outcome = event
        assert outcome is not None  # `_run_tool` ends with the outcome or raises
        if isinstance(outcome, Pending):
            yield ToolPending(tool_call_id=call.id, name=call.name)
            return
        note = await agent.hooks.post_tool_call(call, outcome, session=session)
        if note is not None:
            notes.append(note)

    content = render_outcome(outcome)
    # Logged before it is yielded, so a consumer that persists on `ToolResult`
    # never sees an assistant `tool_calls` without its answer.
    session.append(
        ToolResultEvent(
            turn=turn,
            step=step,
            message=ToolMessage(tool_call_id=call.id, content=content),
            error=None if isinstance(outcome, Ok) else outcome.code,  # the typed code
            ui=outcome.ui if isinstance(outcome, Ok) else None,
        )
    )
    yield ToolResult(tool_call_id=call.id, name=call.name, content=render_text(content))


async def _run_tool(
    agent: LoopAgent, call: ToolCall, *, session: Session
) -> AsyncIterator[ToolProgress | ToolOutcome]:
    """Run the tool: its progress as it reports it, then its outcome, last.

    A task plus a queue, because a generator can only yield from its own
    frame and the progress callback fires inside the tool. The sentinel the
    task posts on its way out is what ends the drain; FIFO order is what
    keeps every report ahead of the outcome.
    """
    # Unbounded: never stall the tool.
    queue: asyncio.Queue[ToolProgress | None] = asyncio.Queue()

    async def report(*, percent: float | None, message: str | None) -> None:
        queue.put_nowait(
            ToolProgress(tool_call_id=call.id, name=call.name, percent=percent, message=message)
        )

    async def run() -> ToolOutcome:
        try:
            assert agent.tools is not None  # a call cannot arrive without a pipeline
            # Folded per call, like the offer is per step: a schema read by an
            # earlier call of this step counts for the next one.
            return await agent.tools.execute(
                call, progress=report, tools_selected=session.tools_selected()
            )
        finally:
            queue.put_nowait(None)  # on every path, or the drain below hangs

    task = asyncio.create_task(run())
    try:
        while (event := await queue.get()) is not None:
            yield event
        outcome = await task
    finally:
        # A no-op on normal exit; on a closed consumer or a cancelled turn it
        # is what stops the tool.
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
    yield outcome


def _close(session: Session, turn: int, step: int, reason: TurnEndReason) -> None:
    session.append(StepEnd(turn=turn, step=step))
    session.append(TurnEnd(turn=turn, reason=reason))
