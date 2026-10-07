"""A step's tool calls, from the model's request to their logged results."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from harness.agent.events import ToolPending, ToolProgress, ToolResult
from harness.llm.messages import ApplicationMessage, ToolCall, ToolMessage, render_text
from harness.session.log import Session
from harness.session.models import ApplicationMessageEvent, ToolCallEvent, ToolResultEvent
from harness.session.repair import unknown_result
from harness.tools.definition import BLOCKED, Failure, Ok, Pending, ToolOutcome, render_outcome

if TYPE_CHECKING:
    from harness.agent.service import LoopAgent


@dataclass(frozen=True)
class Reminder:
    """What a hook wants the model told once the step's calls settle."""

    text: str


def settled_result(call_id: str, outcome: Ok | Failure, *, turn: int, step: int) -> ToolResultEvent:
    """A finished call's outcome as the log records it."""
    return ToolResultEvent(
        turn=turn,
        step=step,
        message=ToolMessage(tool_call_id=call_id, content=render_outcome(outcome)),
        error=None if isinstance(outcome, Ok) else outcome.code,
        ui=outcome.ui if isinstance(outcome, Ok) else None,
    )


async def run_tool_calls(
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
                _answer_call(
                    agent,
                    call,
                    session=session,
                    turn=turn,
                    step=step,
                    approved=call.name in session.tools_granted(),
                )
            ) as events:
                async for event in events:
                    if isinstance(event, Reminder):
                        notes.append(event.text)
                        continue
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
            session.append(unknown_result(call.id, turn=turn, step=step))


async def _answer_call(
    agent: LoopAgent,
    call: ToolCall,
    *,
    session: Session,
    turn: int,
    step: int,
    approved: bool,
) -> AsyncIterator[ToolProgress | ToolResult | ToolPending | Reminder]:
    """Any `ToolProgress`, then a `ToolPending`, or an optional `Reminder` then a `ToolResult`."""
    refusal = await agent.hooks.pre_tool_call(call, session=session)
    outcome: ToolOutcome | None = None
    if refusal is not None:
        outcome = Failure(BLOCKED, refusal)
    else:
        async with aclosing(_execute(agent, call, session=session, approved=approved)) as events:
            async for event in events:
                if isinstance(event, ToolProgress):
                    yield event
                else:
                    outcome = event
        assert outcome is not None
        if isinstance(outcome, Pending):
            yield ToolPending(tool_call_id=call.id, name=call.name)
            return
        note = await agent.hooks.post_tool_call(call, outcome, session=session)
        if note is not None:
            yield Reminder(note)

    result = settled_result(call.id, outcome, turn=turn, step=step)
    session.append(result)
    yield ToolResult(
        tool_call_id=call.id, name=call.name, content=render_text(result.message.content)
    )


async def run_approved_call(
    agent: LoopAgent, call: ToolCall, *, session: Session, turn: int
) -> AsyncIterator[ToolProgress | ToolResult]:
    """An approved call as the resumed turn's first step; a cancel still leaves it answered."""
    notes: list[str] = []
    answered = False
    try:
        async with aclosing(
            _answer_call(agent, call, session=session, turn=turn, step=0, approved=True)
        ) as events:
            async for event in events:
                if isinstance(event, ToolResult):
                    answered = True
                    yield event
                elif isinstance(event, ToolProgress):
                    yield event
                elif isinstance(event, Reminder):
                    notes.append(event.text)
        if notes:
            session.append(
                ApplicationMessageEvent(
                    turn=turn, message=ApplicationMessage(content="\n\n".join(notes))
                )
            )
    finally:
        if not answered:
            session.append(unknown_result(call.id, turn=turn, step=0))


async def _execute(
    agent: LoopAgent, call: ToolCall, *, session: Session, approved: bool
) -> AsyncIterator[ToolProgress | ToolOutcome]:
    """Run the tool: its progress as it reports it, then its outcome, last."""
    queue: asyncio.Queue[ToolProgress | None] = asyncio.Queue()

    async def report(*, percent: float | None, message: str | None) -> None:
        queue.put_nowait(
            ToolProgress(tool_call_id=call.id, name=call.name, percent=percent, message=message)
        )

    async def run() -> ToolOutcome:
        try:
            assert agent.tools is not None
            if approved:
                return await agent.tools.approve(call, progress=report)
            return await agent.tools.execute(
                call, progress=report, tools_selected=session.tools_selected()
            )
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run())
    try:
        while (event := await queue.get()) is not None:
            yield event
        outcome = await task
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
    yield outcome
