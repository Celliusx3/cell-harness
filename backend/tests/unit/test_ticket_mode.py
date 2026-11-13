"""A ticket keeps the chat's mode from its accept, so a restart starts it in that mode."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from harness.bots import ASSISTANT_ID
from harness.tickets.domain.models import Ticket, TicketsFile
from harness.tickets.repository.ticket_repository import TicketRepository
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import WorkerEnd
from harness.tools import ApprovalMode
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import durable_service, heard_nowhere, no_bots, run_service

READY = WorkerEnd(state="ready", text="done", question=None)


@dataclass
class ModeWorkers:
    modes: list[ApprovalMode] = field(default_factory=list)

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
        self.modes.append(mode)
        return READY

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd:
        return READY


def tickets_on(repository: TicketRepository, workers: ModeWorkers, tmp_path) -> TicketService:
    service = durable_service(tmp_path / "sessions")
    bots = no_bots(service)
    return TicketService(
        repository,
        bots,
        run_service(service, ScriptedClient([]), bots=bots),
        worker=workers,
        logs=service,
        follow=heard_nowhere,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        ids=lambda: "t1",
    )


async def test_a_queued_ticket_restarts_in_the_mode_it_was_accepted_in(tmp_path) -> None:
    repository = TicketRepository(tmp_path / "tickets.json")
    workers = ModeWorkers()
    accepting = tickets_on(repository, workers, tmp_path)
    ticket = accepting.accept(bot_id=ASSISTANT_ID, title="T", task="do it", mode="auto")
    await accepting.aclose()
    repository.write(TicketsFile(tickets=(ticket.model_copy(update={"state": "queued"}),)))

    restarted = tickets_on(repository, workers, tmp_path)
    restarted.recover()
    for _ in range(20):
        await asyncio.sleep(0)

    assert repository.read().tickets[0].mode == "auto"
    assert workers.modes[-1] == "auto"
    await restarted.aclose()


def test_a_ticket_saved_before_modes_were_kept_asks() -> None:
    saved = '{"id": "t1", "bot_id": "b", "title": "T", "task": "t", "state": "queued", '
    saved += '"created_at": "2026-01-01T00:00:00Z"}'

    assert Ticket.model_validate_json(saved).mode == "ask"
