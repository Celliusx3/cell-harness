"""One tool call, from the model's request to its logged result."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import TYPE_CHECKING

from harness.agent.events import ToolPending, ToolProgress, ToolResult
from harness.llm.messages import ToolCall, ToolMessage, render_text
from harness.session.log import Session
from harness.session.models import ToolResultEvent
from harness.tools.definition import BLOCKED, Failure, Ok, Pending, ToolOutcome, render_outcome

if TYPE_CHECKING:
    from harness.agent.loop import LoopAgent


async def tool_events(
    agent: LoopAgent,
    call: ToolCall,
    *,
    session: Session,
    turn: int,
    step: int,
    notes: list[str],
) -> AsyncIterator[ToolProgress | ToolResult | ToolPending]:
    """One call: zero or more `ToolProgress`, then exactly one `ToolResult` or `ToolPending`."""
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
        assert outcome is not None
        if isinstance(outcome, Pending):
            yield ToolPending(tool_call_id=call.id, name=call.name)
            return
        note = await agent.hooks.post_tool_call(call, outcome, session=session)
        if note is not None:
            notes.append(note)

    content = render_outcome(outcome)
    session.append(
        ToolResultEvent(
            turn=turn,
            step=step,
            message=ToolMessage(tool_call_id=call.id, content=content),
            error=None if isinstance(outcome, Ok) else outcome.code,
            ui=outcome.ui if isinstance(outcome, Ok) else None,
        )
    )
    yield ToolResult(tool_call_id=call.id, name=call.name, content=render_text(content))


async def _run_tool(
    agent: LoopAgent, call: ToolCall, *, session: Session
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
