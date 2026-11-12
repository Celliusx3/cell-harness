"""A ticket's worker: a copy of a runtime, run to its end in a session log of its own."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import dataclass

from harness.prompts import TICKET_DID_NOT_FINISH, WORKER_INTRO
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.runtime.service import Runtime
from harness.session.log import Session
from harness.session.models import (
    ApprovalModeChanged,
    SessionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStart,
)
from harness.session.service import SessionService
from harness.tickets.models import ReportState, Ticket
from harness.tools.models.decision import ApprovalMode
from harness.tools.native.tickets.models import TicketReportArgs
from harness.tools.native.tickets.report import TICKET_REPORT


@dataclass(frozen=True)
class WorkerEnd:
    """How a worker's turn ended: the state reported, its summary, and any question it asks."""

    state: ReportState
    text: str
    question: str | None


@dataclass(frozen=True)
class Workers:
    """Runs each ticket as `runtime`, logging its steps in `sessions` as `ticket-<id>`."""

    runtime: Runtime
    sessions: SessionService

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
        """Run `ticket`'s task for its bot in `mode`, in a new session, and report its end."""
        session = await self.sessions.create(worker_session_id(ticket.id))
        session.append(ApprovalModeChanged(mode=mode))
        return await self._turn(ticket, ticket.task, session)

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd:
        """Run the next turn on `prompt` in `ticket`'s session, under the mode its log holds."""
        session = await self.sessions.resume(worker_session_id(ticket.id))
        return await self._turn(ticket, prompt, session)

    async def _turn(self, ticket: Ticket, prompt: str, session: Session) -> WorkerEnd:
        worker = dataclasses.replace(
            self.runtime,
            guidance=WORKER_INTRO.format(title=ticket.title) + self.runtime.guidance,
            checkpoint=self.sessions.flush,
        )
        last: TurnEvent | None = None
        try:
            async with aclosing(
                worker.run(prompt, session=session, bot_id=ticket.bot_id)
            ) as events:
                async for event in events:
                    last = event
        finally:
            await self.sessions.flush(session)
        return worker_end(last, kept_report(session.events()))


def worker_session_id(ticket_id: str) -> str:
    """The id of the session `ticket_id`'s worker logs its steps in."""
    return f"ticket-{ticket_id}"


def kept_report(events: Sequence[SessionEvent]) -> TicketReportArgs | None:
    """The last report of the last turn that `ticket_report` accepted, `progress` skipped."""
    asked: dict[str, str] = {}
    kept: TicketReportArgs | None = None
    for event in events:
        if isinstance(event, TurnStart):
            asked, kept = {}, None
        elif isinstance(event, ToolCallEvent) and event.call.name == TICKET_REPORT:
            asked = {**asked, event.call.id: event.call.arguments}
        elif isinstance(event, ToolResultEvent) and event.error is None:
            arguments = asked.get(event.message.tool_call_id)
            report = None if arguments is None else TicketReportArgs.model_validate_json(arguments)
            if report is not None and report.state != "progress":
                kept = report
    return kept


def worker_end(ending: TurnEvent | None, kept: TicketReportArgs | None) -> WorkerEnd:
    """The kept report when the turn completed, else `ready` with its reply; `failed` otherwise."""
    if not isinstance(ending, AgentCompleted):
        return WorkerEnd(state="failed", text=TICKET_DID_NOT_FINISH, question=None)
    if kept is None:
        return WorkerEnd(state="ready", text=ending.text, question=None)
    return WorkerEnd(state=kept.state, text=kept.summary, question=kept.question)
