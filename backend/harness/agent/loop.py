"""`LoopAgent` — gather context, act, repeat until nothing is owed.

One **step** is one model request plus the tools it asked for. A **turn** is one
or more steps: if a step ends with tool calls, their results are appended and the
model is asked again; if it ends without, the turn is over.

**The discipline this file exists to hold:** history comes from
`derive_messages(session.events())`, recomputed before *every* step — never from
a list this class accumulated. That is what makes resume, fork, and compaction
consequences of the log rather than features to build and keep in sync. It also
means a tool result reaches the next request by being *logged*, with no separate
path for the loop to get wrong.

The system prompt is deliberately not logged and not part of history. It is
prepended per request, which is what lets it reflect the agent running *this*
turn — including, from phase 9, a different agent after routing.

`LoopAgent` is a frozen dataclass and holds no state: the `Session` passed to
`run()` owns everything that survives the call. Engine and state holder are
separate objects, so two turns against two sessions cannot interleave.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass, field

from harness.agent.events import AgentCompleted, AgentFailed, ToolProgress, ToolResult
from harness.llm.client import LLMClient
from harness.llm.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from harness.llm.stream import Completed, Failed, TextChunk, ToolCallChunk
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.models import (
    AssistantChunk,
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repair import REPAIRED, TOOL_OUTCOME_UNKNOWN
from harness.tools.definition import Ok, ToolOutcome, render_outcome
from harness.tools.pipeline import ToolPipeline

# What a stream that produced no terminal event is reported as. An adapter owes
# exactly one (see `llm.client`); treating a missing one as a failure is how that
# contract is enforced rather than merely documented.
NO_TERMINAL = "stream ended without a terminal event"

# What a tool call that never finished leaves behind. A provider requires exactly
# one result per call, so an abandoned turn must still answer every call it made
# or the next request is rejected outright.
#
# The loop only ever owes results for calls it *dispatched* — `tool/call` is
# logged immediately before the tool runs — so the outcome is genuinely unknown
# and never "not started". Same words as `session.repair` uses for a crash,
# because it is the same situation from the model's side: the tab closed or the
# process died, and either way it must not assume the work did not happen.
INTERRUPTED_RESULT = TOOL_OUTCOME_UNKNOWN

# A backstop against a bug in THIS loop, not a convergence strategy.
#
# DeepSeek Harness has no step cap at all. Its answer to a model that repeats
# itself is `repeat-tool-reminder`: an advisory nudge at 3, 5 and 8 consecutive
# identical calls that never blocks anything, leaving the decision with the
# model. That is the better answer to the model-misbehaviour half of the problem,
# and it arrives with the loop guardrail.
#
# What it does not cover is us: if this loop ever fails to clear `owed`, or a
# tool always returns something that provokes another call, an advisory message
# to the model changes nothing. So the cap stays until something enforces a
# bound, and 60 is set above real multi-step work rather than near it — it should
# never fire in normal use, and firing is a bug report.
DEFAULT_MAX_STEPS = 60


@dataclass(frozen=True)
class LoopAgent:
    """An agent that answers by running the tool loop."""

    name: str
    model: str
    client: LLMClient
    tools: ToolPipeline | None = None
    system_prompt: str = ""
    max_steps: int = field(default=DEFAULT_MAX_STEPS)
    # Called immediately before each model request, to make everything logged so
    # far durable. A prompt that is not yet on disk is a reply to a question the
    # log cannot show, so this is the one moment durability must not lag.
    #
    # A callable rather than the store itself: the loop depends on "make this
    # durable", not on how. `None` is a session that is never written down —
    # every test that does not care about storage.
    checkpoint: Callable[[Session], Awaitable[None]] | None = None

    def _request_messages(self, session: Session) -> list[Message]:
        """What this request sees: the system prompt, then the conversation.

        Derived at call time, so it already contains the user message, every
        earlier step's reply, and every tool result — in log order.
        """
        history = derive_messages(session.events())
        if not self.system_prompt:
            return history
        return [SystemMessage(content=self.system_prompt), *history]

    async def run(
        self, user_input: str, *, session: Session
    ) -> AsyncIterator[
        TextChunk | ToolCallChunk | ToolProgress | ToolResult | AgentCompleted | AgentFailed
    ]:
        """Run one turn, streaming its events.

        Yields the reply's chunks live, tool progress and results as they settle,
        then exactly one terminal. Calling it again continues the conversation —
        the log carries everything, so there is nothing to thread between turns.
        """
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        session.append(UserMessageEvent(turn=turn, message=UserMessage(content=user_input)))

        # Text streamed but not yet written to the log. A step normally records
        # its assistant message only when the request *completes*, so without
        # this every early exit would discard the half-answer the user watched
        # appear. The `finally` is what rescues it.
        partial = ""
        # Calls this step asked for that have no result yet. A provider rejects a
        # history containing one, so an abandoned turn must answer them.
        owed: list[ToolCall] = []
        # Whether this turn already recorded its own `turn/end`. The `finally`
        # runs on every path, and a turn closed twice is a log that contradicts
        # itself.
        closed = False
        step = 0
        # Text accumulated across steps, so a tool-calling step's preamble
        # ("Let me check the time…") survives into the final answer.
        answer = ""

        try:
            for step in range(self.max_steps):
                session.append(StepStart(turn=turn, step=step))
                partial = ""
                owed = []

                # Read fresh each step, not once up front, so a tool contributed
                # by a source that connected mid-turn is offered immediately.
                specs = self.tools.specs() if self.tools else None
                messages = self._request_messages(session)
                if self.checkpoint is not None:
                    await self.checkpoint(session)

                completed: Completed | None = None
                failed: Failed | None = None

                # `aclosing`, not a bare `async for`: when this generator is
                # closed mid-stream, GeneratorExit unwinds *this* frame but would
                # leave the adapter's to the garbage collector's asyncgen hook —
                # with the HTTP response still open in the meantime.
                async with aclosing(
                    self.client.stream_completion(messages, self.model, tools=specs)
                ) as stream:
                    async for event in stream:
                        # Every stream event is logged verbatim, terminals
                        # included: the log reproduces the stream, with no
                        # special cases to get wrong.
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

                if failed is not None:
                    session.append(StepEnd(turn=turn, step=step))
                    session.append(TurnEnd(turn=turn, reason="failed"))
                    closed = True
                    yield AgentFailed(reason=failed.reason)
                    return

                if completed is None:
                    session.append(StepEnd(turn=turn, step=step))
                    session.append(TurnEnd(turn=turn, reason="failed"))
                    closed = True
                    yield AgentFailed(reason=NO_TERMINAL)
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
                # In the log now, so it is no longer pending — leaving it set
                # would append it a second time if a tool below is interrupted.
                partial = ""

                if not completed.tool_calls:
                    session.append(StepEnd(turn=turn, step=step))
                    session.append(TurnEnd(turn=turn, reason="completed"))
                    closed = True
                    yield AgentCompleted(text=answer)
                    return

                owed = list(completed.tool_calls)
                # Serial, one call at a time. `_tool_events` adds fan-in *within*
                # a call (progress interleaved with the result), not parallelism
                # across calls — that waits for a seam where overlap is
                # meaningful and testable.
                for call in completed.tool_calls:
                    session.append(ToolCallEvent(turn=turn, step=step, call=call))
                    # The second durability checkpoint, and the reason
                    # `tool/call` is written before the tool runs: if the process
                    # dies inside a side effect, the log must show we were about
                    # to cause one. Without this, recovery could not tell "never
                    # started" from "may have completed" — and would have to
                    # assume the safer, more useless of the two.
                    if self.checkpoint is not None:
                        await self.checkpoint(session)
                    async with aclosing(
                        self._tool_events(call, session=session, turn=turn, step=step)
                    ) as events:
                        async for event in events:
                            if isinstance(event, ToolResult):
                                owed.remove(call)
                            yield event

                session.append(StepEnd(turn=turn, step=step))

            # Fell out of the step budget.
            session.append(TurnEnd(turn=turn, reason="failed"))
            closed = True
            yield AgentFailed(reason=f"exceeded {self.max_steps} steps without completing")
        finally:
            # `finally` rather than an exception handler because the abandoned
            # paths are not raises of the same kind: closing this generator
            # raises GeneratorExit, cancelling the task consuming it raises
            # CancelledError, and neither is an `except Exception`.
            #
            # Nothing is awaited here — an async generator may not yield during
            # cleanup, and `append` is synchronous.
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
                # Every call this step made must have a result, or the next
                # request is rejected outright.
                for call in owed:
                    session.append(
                        ToolResultEvent(
                            turn=turn,
                            step=step,
                            message=ToolMessage(tool_call_id=call.id, content=INTERRUPTED_RESULT),
                            error=REPAIRED,
                        )
                    )
                session.append(StepEnd(turn=turn, step=step))
                session.append(TurnEnd(turn=turn, reason="cancelled"))

    async def _tool_events(
        self, call: ToolCall, *, session: Session, turn: int, step: int
    ) -> AsyncIterator[ToolProgress | ToolResult]:
        """One tool call as a stream: zero or more `ToolProgress`, then exactly
        one `ToolResult`.

        The call runs as a *task* rather than a bare `await` because a generator
        can only yield from its own frame — a progress callback firing inside the
        tool has no way to put an event on this stream. So the work goes to a
        task, this frame drains a queue while it runs, and a sentinel the task
        always posts on its way out is what ends the drain.

        Ordering is by construction: the queue is FIFO, every report is awaited
        *inside* the tool, and the sentinel is enqueued only once it has
        returned — so no `ToolProgress` can follow the `ToolResult`.

        The queue is unbounded on purpose. A bounded one would make `report`
        block, stalling the tool on a consumer that is not reading; a chatty tool
        is throttled at its source instead.
        """
        queue: asyncio.Queue[ToolProgress | None] = asyncio.Queue()

        async def report(*, percent: float | None, message: str | None) -> None:
            queue.put_nowait(
                ToolProgress(tool_call_id=call.id, name=call.name, percent=percent, message=message)
            )

        async def run() -> ToolOutcome:
            try:
                assert self.tools is not None  # a call cannot arrive without a pipeline
                return await self.tools.execute(call, progress=report)
            finally:
                # On success, failure and cancellation alike: this sentinel is
                # the only thing that releases the drain below, so any path that
                # skipped it would hang the turn forever.
                queue.put_nowait(None)

        task = asyncio.create_task(run())
        try:
            while (event := await queue.get()) is not None:
                yield event
            outcome = await task
        finally:
            # Normal exit: the task is done, so this is a no-op. Abnormal exit (a
            # closed consumer, or the turn cancelled): this is what stops the
            # tool — otherwise the work outlives the request that asked for it.
            task.cancel()
            with contextlib.suppress(BaseException):
                await task

        content = render_outcome(outcome)
        # The log is written *before* the event goes out, so a consumer that
        # persists on `ToolResult` can rely on the result already being there —
        # otherwise it records an assistant `tool_calls` with no answer, which
        # the provider rejects on the next request.
        session.append(
            ToolResultEvent(
                turn=turn,
                step=step,
                message=ToolMessage(tool_call_id=call.id, content=content),
                # The typed code, not the rendered string: the phase-8 guardrail
                # counts failures by identity, and a tool that phrased its error
                # differently must not become invisible to it.
                error=None if isinstance(outcome, Ok) else outcome.code,
            )
        )
        yield ToolResult(tool_call_id=call.id, name=call.name, content=content)
