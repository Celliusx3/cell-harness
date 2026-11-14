"""A ticket's worker: a copy of a runtime, run to its end in a session log of its own."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from harness.runtime.events import AgentCompleted, AgentFailed, AgentPending, TurnEvent
from harness.runtime.run_to_end import HelperAnswer, HelperTurn, resume_to_end, run_to_end
from harness.runtime.service import Runtime
from harness.session.domain.log import Session
from harness.session.domain.models import (
    ApprovalModeChange,
    SessionEvent,
    TicketAsk,
    TicketReport,
    ToolCallEvent,
    ToolResultEvent,
    TurnStart,
)
from harness.session.service.session_service import SessionService
from harness.tickets.domain.models import ReportState, Ticket
from harness.tickets.domain.prompts import (
    APPROVAL_QUESTION,
    APPROVAL_WAITING,
    TICKET_DID_NOT_FINISH,
    TICKET_TURN_FAILED,
    WORKER_INTRO,
)
from harness.tools import Approval, Failure, Ok
from harness.tools.domain.decision import ApprovalMode
from harness.tools.native.tickets.models import TicketReportArgs
from harness.tools.native.tickets.report import TICKET_REPORT


@dataclass(frozen=True)
class WorkerEnd:
    """How a worker's turn ended: the state reported, its summary, and any question it asks."""

    state: ReportState
    text: str
    question: str | None
    ask: TicketAsk = "text"
    options: tuple[str, ...] | None = None
    secret_name: str | None = None
    approval_call_id: str | None = None
    approval_tool: str | None = None

    def report(self, ticket: Ticket) -> TicketReport:
        """This end as `ticket`'s bot hears it."""
        return TicketReport(
            ticket_id=ticket.id,
            title=ticket.title,
            state=self.state,
            text=self.text,
            question=self.question,
            ask=self.ask,
            options=self.options,
            secret_name=self.secret_name,
            approval_call_id=self.approval_call_id,
            approval_tool=self.approval_tool,
        )


class TicketWorker(Protocol):
    """Runs a ticket's first turn in `mode`, and each next turn on the same log, to its end."""

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd: ...

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd: ...

    async def approve(
        self, ticket: Ticket, call_id: str, outcome: Ok | Failure | Approval
    ) -> WorkerEnd: ...


@dataclass(frozen=True)
class RuntimeTicketWorker:
    """Runs each ticket as `runtime`, logging its steps in `sessions` as `ticket-<id>`."""

    runtime: Runtime
    sessions: SessionService

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
        """Run `ticket`'s task for its bot in `mode`, in a new session, and report its end."""
        session = await self.sessions.create(worker_session_id(ticket.id))
        session.append(ApprovalModeChange(mode=mode))
        return await self._run_turn(ticket, ticket.task, session)

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd:
        """Run the next turn on `prompt` in `ticket`'s session, under the mode its log holds."""
        session = await self.sessions.resume(worker_session_id(ticket.id))
        return await self._run_turn(ticket, prompt, session)

    async def approve(
        self, ticket: Ticket, call_id: str, outcome: Ok | Failure | Approval
    ) -> WorkerEnd:
        """Answer the call `ticket`'s worker waits on with the person's decision, to its end."""
        session = await self.sessions.resume(worker_session_id(ticket.id))
        intro = WORKER_INTRO.format(title=ticket.title)
        answer = HelperAnswer(intro=intro, call_id=call_id, outcome=outcome, bot_id=ticket.bot_id)
        last = await resume_to_end(self.runtime, self.sessions, session, answer)
        return worker_end(last, last_accepted_report(session.events()))

    async def _run_turn(self, ticket: Ticket, prompt: str, session: Session) -> WorkerEnd:
        intro = WORKER_INTRO.format(title=ticket.title)
        turn = HelperTurn(intro=intro, prompt=prompt, bot_id=ticket.bot_id)
        last = await run_to_end(self.runtime, self.sessions, session, turn)
        return worker_end(last, last_accepted_report(session.events()))


def worker_session_id(ticket_id: str) -> str:
    """The id of the session `ticket_id`'s worker logs its steps in."""
    return f"ticket-{ticket_id}"


def last_accepted_report(events: Sequence[SessionEvent]) -> TicketReportArgs | None:
    """The last report of the last turn that `ticket_report` accepted, `progress` skipped."""
    arguments_by_call_id: dict[str, str] = {}
    kept: TicketReportArgs | None = None
    for event in events:
        if isinstance(event, TurnStart):
            arguments_by_call_id, kept = {}, None
        elif isinstance(event, ToolCallEvent) and event.call.name == TICKET_REPORT:
            arguments_by_call_id = {**arguments_by_call_id, event.call.id: event.call.arguments}
        elif isinstance(event, ToolResultEvent) and event.error is None:
            arguments = arguments_by_call_id.get(event.message.tool_call_id)
            report = None if arguments is None else TicketReportArgs.model_validate_json(arguments)
            if report is not None and report.state != "progress":
                kept = report
    return kept


def worker_end(ending: TurnEvent | None, kept: TicketReportArgs | None) -> WorkerEnd:
    """The kept report when the turn completed, else `ready` with its reply; `failed` otherwise.

    A worker is offered no client tool, so a turn of its that waits waits for an approval.
    """
    if isinstance(ending, AgentPending):
        return WorkerEnd(
            state="blocked",
            text=APPROVAL_WAITING.format(tool=ending.name),
            question=APPROVAL_QUESTION.format(tool=ending.name),
            ask="approval",
            approval_call_id=ending.tool_call_id,
            approval_tool=ending.name,
        )
    if isinstance(ending, AgentFailed):
        return WorkerEnd(
            state="failed", text=TICKET_TURN_FAILED.format(reason=ending.reason), question=None
        )
    if not isinstance(ending, AgentCompleted):
        return WorkerEnd(state="failed", text=TICKET_DID_NOT_FINISH, question=None)
    if kept is None:
        return WorkerEnd(state="ready", text=ending.text, question=None)
    return WorkerEnd(
        state=kept.state,
        text=kept.summary,
        question=kept.question,
        ask=kept.ask,
        options=kept.options,
        secret_name=kept.secret_name,
    )
