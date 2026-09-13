"""`LoopAgent` — gather context, act, repeat until nothing is owed.

One **step** is one model request plus the tools it asked for. A **turn** is one
or more steps: if a step ends with tool calls, their results are appended and the
model is asked again; if it ends without, the turn is over.

History comes from `derive_messages(session.events())`, recomputed before every
step — never from a list this class accumulated. That is what makes resume,
fork, and compaction consequences of the log, and it means a tool result reaches
the next request by being *logged*. The system prompt is prepended per request
and never logged, so it can reflect the agent running *this* turn.

`LoopAgent` is frozen and holds no state: the `Session` passed to `run()` owns
everything that survives the call.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass

from harness.agent.events import AgentCompleted, AgentFailed, ToolProgress, ToolResult
from harness.agent.hooks import HookChain
from harness.llm.client import LLMClient
from harness.llm.messages import (
    ApplicationMessage,
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
    render_text,
)
from harness.llm.stream import Completed, Failed, TextChunk, ToolCallChunk
from harness.session.derive import derive_messages
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
    TurnStart,
    UserMessageEvent,
)
from harness.session.repair import REPAIRED, TOOL_OUTCOME_UNKNOWN
from harness.tools.definition import BLOCKED, Failure, Ok, ToolOutcome, render_outcome
from harness.tools.pipeline import ToolPipeline

# An adapter owes exactly one terminal event; a missing one is a failure, not a quirk.
NO_TERMINAL = "stream ended without a terminal event"

# A provider requires one result per call, so an abandoned turn must answer every
# call it dispatched. Same words as a crash repair: the outcome is unknown either way.
INTERRUPTED_RESULT = TOOL_OUTCOME_UNKNOWN


@dataclass(frozen=True)
class LoopAgent:
    """An agent that answers by running the tool loop."""

    name: str
    model: str
    client: LLMClient
    tools: ToolPipeline | None = None
    system_prompt: str = ""
    # Asked before and after every tool call. Empty by default: the composition
    # root decides what is installed, and the loop does not know what it is.
    hooks: HookChain = HookChain()
    # Makes the log durable before each model request and each tool call — the
    # two moments a lost write would leave the log unable to explain what followed.
    checkpoint: Callable[[Session], Awaitable[None]] | None = None

    def _request_messages(self, session: Session) -> list[Message]:
        history = derive_messages(session.events())
        if not self.system_prompt:
            return history
        return [SystemMessage(content=self.system_prompt), *history]

    async def run(
        self, user_input: str, *, session: Session
    ) -> AsyncIterator[
        TextChunk | ToolCallChunk | ToolProgress | ToolResult | AgentCompleted | AgentFailed
    ]:
        """Run one turn: the reply's chunks live, tool progress and results as
        they settle, then exactly one terminal."""
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        session.append(UserMessageEvent(turn=turn, message=UserMessage(content=user_input)))

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
                specs = self.tools.specs(session.tools_selected()) if self.tools else None
                messages = self._request_messages(session)
                if self.checkpoint is not None:
                    await self.checkpoint(session)

                completed: Completed | None = None
                failed: Failed | None = None
                # `aclosing`: closing this generator mid-stream must close the
                # adapter's too, or its HTTP response outlives the turn.
                async with aclosing(
                    self.client.stream_completion(messages, self.model, tools=specs)
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
                for call in completed.tool_calls:
                    # `tool/call` is logged and made durable *before* the tool
                    # runs, so a crash mid-side-effect is recoverable as "may have
                    # happened" rather than "never started".
                    session.append(ToolCallEvent(turn=turn, step=step, call=call))
                    if self.checkpoint is not None:
                        await self.checkpoint(session)
                    async with aclosing(
                        self._tool_events(call, session=session, turn=turn, step=step, notes=notes)
                    ) as events:
                        async for event in events:
                            if isinstance(event, ToolResult):
                                owed.remove(call)
                            yield event

                if notes:
                    session.append(
                        ApplicationMessageEvent(
                            turn=turn, message=ApplicationMessage(content="\n\n".join(notes))
                        )
                    )
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
        self, call: ToolCall, *, session: Session, turn: int, step: int, notes: list[str]
    ) -> AsyncIterator[ToolProgress | ToolResult]:
        """One call: zero or more `ToolProgress`, then exactly one `ToolResult`.
        What a hook wants the model told goes on `notes`.

        The hooks run here, after `tool/call` was logged, so a refused call
        still has its call and result on record and the tool never starts.
        """
        refusal = await self.hooks.pre_tool_call(call, session=session)
        outcome: ToolOutcome | None = None
        if refusal is not None:
            outcome = Failure(BLOCKED, refusal)
        else:
            async with aclosing(self._run_tool(call, session=session)) as events:
                async for event in events:
                    if isinstance(event, ToolProgress):
                        yield event
                    else:
                        outcome = event
            assert outcome is not None  # `_run_tool` ends with the outcome or raises
            note = await self.hooks.post_tool_call(call, outcome, session=session)
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
            )
        )
        yield ToolResult(tool_call_id=call.id, name=call.name, content=render_text(content))

    async def _run_tool(
        self, call: ToolCall, *, session: Session
    ) -> AsyncIterator[ToolProgress | ToolOutcome]:
        """Run the tool: its progress as it reports it, then its outcome, last.

        A task plus a queue, because a generator can only yield from its own
        frame and the progress callback fires inside the tool. The sentinel the
        task posts on its way out is what ends the drain; FIFO order is what
        keeps every report ahead of the outcome.
        """
        queue: asyncio.Queue[ToolProgress | None] = (
            asyncio.Queue()
        )  # unbounded: never stall the tool

        async def report(*, percent: float | None, message: str | None) -> None:
            queue.put_nowait(
                ToolProgress(tool_call_id=call.id, name=call.name, percent=percent, message=message)
            )

        async def run() -> ToolOutcome:
            try:
                assert self.tools is not None  # a call cannot arrive without a pipeline
                # Folded per call, like the offer is per step: a schema read by an
                # earlier call of this step counts for the next one.
                return await self.tools.execute(
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
