"""A ticket's worker: a copy of a runtime, run to its end in a session log of its own."""

from __future__ import annotations

import dataclasses
from contextlib import aclosing
from dataclasses import dataclass

from harness.prompts import TICKET_DID_NOT_FINISH, WORKER_INTRO
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.runtime.service import Runtime
from harness.session.models import ApprovalModeChanged
from harness.session.service import SessionService
from harness.tickets.models import Ticket, TicketState
from harness.tools.models.decision import ApprovalMode


@dataclass(frozen=True)
class WorkerEnd:
    """How a worker's turn ended: the ticket's state, and the text its bot is told."""

    state: TicketState
    text: str


@dataclass(frozen=True)
class Workers:
    """Runs each ticket as `runtime`, logging its steps in `sessions` as `ticket-<id>`."""

    runtime: Runtime
    sessions: SessionService

    async def __call__(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
        """Run `ticket`'s task for its bot in `mode`, in a new session, and report its end."""
        session = await self.sessions.create(worker_session_id(ticket.id))
        session.append(ApprovalModeChanged(mode=mode))
        worker = dataclasses.replace(
            self.runtime,
            guidance=WORKER_INTRO.format(title=ticket.title) + self.runtime.guidance,
            checkpoint=self.sessions.flush,
        )
        last: TurnEvent | None = None
        try:
            async with aclosing(
                worker.run(ticket.task, session=session, bot_id=ticket.bot_id)
            ) as events:
                async for event in events:
                    last = event
        finally:
            await self.sessions.flush(session)
        return worker_end(last)


def worker_session_id(ticket_id: str) -> str:
    """The id of the session `ticket_id`'s worker logs its steps in."""
    return f"ticket-{ticket_id}"


def worker_end(ending: TurnEvent | None) -> WorkerEnd:
    """`done` with the final reply when the turn completed; `failed` however else it ended."""
    if isinstance(ending, AgentCompleted):
        return WorkerEnd(state="done", text=ending.text)
    return WorkerEnd(state="failed", text=TICKET_DID_NOT_FINISH)
