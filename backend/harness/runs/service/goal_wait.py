"""A goal run's team turn: its bot's turn, then each of its workers' reports heard in it."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass

from harness.groups.domain.goal import GOAL_WAIT_SECONDS
from harness.runs.service.report_inbox import ReportInbox
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.runtime.service import Runtime
from harness.session.domain.log import Session
from harness.session.domain.models import GoalStepEvent, TicketReport, TicketReportEvent


@dataclass
class TeamTurnEnd:
    """How a team turn ended: its last turn's terminal, a wait past the limit, a question."""

    terminal: TurnEvent | None = None
    busy: bool = False
    question: str | None = None


async def team_turn(
    runtime: Runtime,
    session: Session,
    inbox: ReportInbox,
    step: GoalStepEvent,
    first: AsyncIterator[TurnEvent],
    ended: TeamTurnEnd,
) -> AsyncIterator[TurnEvent]:
    """`first`, then a heard turn per report of its bot's workers, until none is left or asks."""
    async with aclosing(_logged_turn(session, step, first, ended)) as events:
        async for event in events:
            yield event
    deadline = asyncio.get_running_loop().time() + GOAL_WAIT_SECONDS
    while isinstance(ended.terminal, AgentCompleted) and ended.question is None:
        report = await _next_report(inbox, step.bot_id, deadline, ended)
        if report is None:
            return
        ended.question = report.question
        if report.ask == "approval":
            session.append(TicketReportEvent(turn=max(session.next_turn() - 1, 0), report=report))
            return
        heard = runtime.hear(report, session=session, bot_id=step.bot_id)
        async with aclosing(_logged_turn(session, step, heard, ended)) as events:
            async for event in events:
                yield event


async def _logged_turn(
    session: Session, step: GoalStepEvent, turn: AsyncIterator[TurnEvent], ended: TeamTurnEnd
) -> AsyncIterator[TurnEvent]:
    """`turn`, logged as part of team turn `step`, its terminal kept in `ended`."""
    session.append(step.model_copy(update={"turn": session.next_turn()}))
    async with aclosing(turn) as events:
        async for event in events:
            ended.terminal = event
            yield event


async def _next_report(
    inbox: ReportInbox, bot_id: str, deadline: float, ended: TeamTurnEnd
) -> TicketReport | None:
    """The next report for `bot_id`; `None` when none is left, or the limit passed and is kept."""
    try:
        async with asyncio.timeout_at(deadline):
            return await inbox.next_for(bot_id)
    except TimeoutError:
        inbox.release(bot_id)
        ended.busy = True
        return None
