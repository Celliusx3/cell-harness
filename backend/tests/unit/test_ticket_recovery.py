"""After a restart, a working ticket starts again with a note; the rest stay as they are."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from harness.bots import ASSISTANT_ID
from harness.tickets.models import Ticket, TicketsFile
from harness.tickets.repository import TicketRepository
from harness.tickets.service import TicketService
from harness.tickets.worker import WorkerEnd
from harness.tools.models.decision import ApprovalMode
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import durable_service, heard_nowhere, run_service
from tests.webapp import bots_in

RECOVERY = (
    "The app restarted while you worked on this ticket. Check your folder and what you already "
    "did before you repeat anything, then carry on."
)
READY = WorkerEnd(state="ready", text="done", question=None)


@dataclass
class RecordingWorkers:
    """Workers that record each turn they are asked for, and end it ready at once."""

    turns: list[tuple[str, str]] = field(default_factory=list)

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
        self.turns.append((ticket.id, "start"))
        return READY

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd:
        self.turns.append((ticket.id, prompt))
        return READY


def ticket(ticket_id: str, state: str) -> Ticket:
    return Ticket(
        id=ticket_id,
        bot_id=ASSISTANT_ID,
        title=ticket_id,
        task="do it",
        state=state,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


async def test_working_tickets_resume_with_a_note_and_queued_ones_start_again(tmp_path) -> None:
    repository = TicketRepository(tmp_path / "tickets.json")
    repository.write(
        TicketsFile(
            tickets=(
                ticket("working", "working"),
                ticket("queued", "queued"),
                ticket("asking", "needs_answer"),
                ticket("done", "done"),
                ticket("stopped", "stopped"),
            )
        )
    )
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    workers = RecordingWorkers()
    tickets = TicketService(
        repository,
        bots,
        run_service(service, ScriptedClient([]), bots=bots),
        worker=workers,
        logs=service,
        follow=heard_nowhere,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        ids=lambda: "new",
    )

    tickets.recover()
    for _ in range(50):
        await asyncio.sleep(0)

    assert sorted(workers.turns) == [("queued", "start"), ("working", RECOVERY)]
    states = {t.id: t.state for t in tickets.of_bot(ASSISTANT_ID)}
    assert (states["asking"], states["done"], states["stopped"]) == (
        "needs_answer",
        "done",
        "stopped",
    )
    await tickets.aclose()
