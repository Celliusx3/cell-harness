"""Running one step's tool calls, and how the step ends: the turn's terminal, or the next step."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from harness.llm import ToolCall
from harness.runtime.events import AgentCompleted, AgentPending, ToolPending, ToolResult, TurnEvent
from harness.runtime.tool_run import run_tool_calls
from harness.session.domain.log import Session
from harness.session.domain.models import StepEnd, TurnEnd, TurnEndReason

if TYPE_CHECKING:
    from harness.runtime.service import Runtime


@dataclass(frozen=True)
class NextStep:
    """Every call in the step settled and none ended the turn: the turn goes on."""


StepEnding = AgentCompleted | AgentPending | NextStep


async def run_step_tools(
    runtime: Runtime,
    session: Session,
    calls: Sequence[ToolCall],
    *,
    turn: int,
    step: int,
    bot_id: str,
) -> AsyncIterator[TurnEvent | StepEnding]:
    """The step's tool events as they happen, then exactly one `StepEnding`."""
    pending: ToolPending | None = None
    ends_turn = False
    async with aclosing(
        run_tool_calls(runtime, calls, session=session, turn=turn, step=step, bot_id=bot_id)
    ) as results:
        async for event in results:
            if isinstance(event, ToolPending):
                pending = event
            ends_turn = ends_turn or (isinstance(event, ToolResult) and event.ends_turn)
            yield event
    if pending is not None:
        close_turn(session, turn, step, "pending")
        yield AgentPending(tool_call_id=pending.tool_call_id, name=pending.name)
    elif ends_turn:
        close_turn(session, turn, step, "completed")
        yield AgentCompleted(text="")
    else:
        session.append(StepEnd(turn=turn, step=step))
        yield NextStep()


def close_turn(session: Session, turn: int, step: int, reason: TurnEndReason) -> None:
    """End the step, then the turn, for `reason`."""
    session.append(StepEnd(turn=turn, step=step))
    session.append(TurnEnd(turn=turn, reason=reason))
