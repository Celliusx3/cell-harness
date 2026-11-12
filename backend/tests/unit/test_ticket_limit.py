"""At most a bot's limit of workers run at once; the rest queue, and an answer always runs."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
from datetime import UTC, datetime

from harness.bots import ASSISTANT_ID
from harness.tickets.models import Ticket
from harness.tickets.repository import TicketRepository
from harness.tickets.service import TicketService
from harness.tickets.worker import WorkerEnd
from harness.tools.models.decision import ApprovalMode
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import durable_service, heard_nowhere, run_service
from tests.webapp import bots_in

READY = WorkerEnd(state="ready", text="done", question=None)
ASKING = WorkerEnd(state="blocked", text="need a choice", question="Which one?")


@dataclass
class HeldWorkers:
    """Workers that each run until the test releases their ticket."""

    first_ends: dict[str, WorkerEnd] = field(default_factory=dict)
    releases: dict[str, asyncio.Event] = field(default_factory=dict)
    started: list[str] = field(default_factory=list)

    def release(self, ticket_id: str) -> None:
        self.releases.setdefault(ticket_id, asyncio.Event()).set()

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
        return await self._turn(ticket, self.first_ends.get(ticket.id))

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd:
        return await self._turn(ticket, None)

    async def _turn(self, ticket: Ticket, at_once: WorkerEnd | None) -> WorkerEnd:
        self.started.append(ticket.id)
        if at_once is not None:
            return at_once
        await self.releases.setdefault(ticket.id, asyncio.Event()).wait()
        self.releases.pop(ticket.id)
        return READY


def tickets_with(tmp_path, workers: HeldWorkers) -> TicketService:
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    count = itertools.count(1)
    return TicketService(
        TicketRepository(tmp_path / "tickets.json"),
        bots,
        run_service(service, ScriptedClient([]), bots=bots),
        worker=workers,
        logs=service,
        follow=heard_nowhere,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        ids=lambda: f"t{next(count)}",
    )


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


def states(tickets: TicketService) -> dict[str, str]:
    return {t.id: t.state for t in tickets.of_bot(ASSISTANT_ID)}


async def test_five_tickets_on_a_limit_of_three_run_three_and_queue_two(tmp_path) -> None:
    workers = HeldWorkers()
    tickets = tickets_with(tmp_path, workers)
    for n in range(5):
        tickets.accept(bot_id=ASSISTANT_ID, title=f"T{n}", task="do it", mode="auto")
    await settle()

    assert workers.started == ["t1", "t2", "t3"]
    assert states(tickets) == {
        "t1": "working",
        "t2": "working",
        "t3": "working",
        "t4": "queued",
        "t5": "queued",
    }

    workers.release("t1")
    await settle()

    assert workers.started == ["t1", "t2", "t3", "t4"]
    assert states(tickets)["t4"] == "working"
    await tickets.aclose()


async def test_an_answer_runs_even_when_every_place_is_taken(tmp_path) -> None:
    workers = HeldWorkers(first_ends={"t1": ASKING})
    tickets = tickets_with(tmp_path, workers)
    tickets.accept(bot_id=ASSISTANT_ID, title="Asks", task="do it", mode="auto")
    await settle()
    assert states(tickets)["t1"] == "needs_answer"
    for n in range(3):
        tickets.accept(bot_id=ASSISTANT_ID, title=f"T{n}", task="do it", mode="auto")
    await settle()

    tickets.answer("t1", "the first one")
    await settle()

    assert workers.started == ["t1", "t2", "t3", "t4", "t1"]
    assert tickets.is_running("t1")
    await tickets.aclose()
