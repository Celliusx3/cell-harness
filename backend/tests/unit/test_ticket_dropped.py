"""A worker that finds nothing to do ends its ticket `dropped`, and the bot is not woken."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from harness.bots import ASSISTANT_ID
from harness.runs.service.run import Run
from harness.tickets.domain.models import Ticket
from harness.tickets.repository.ticket_repository import TicketRepository
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import WorkerEnd
from harness.tools.domain.decision import ApprovalMode
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, run_service
from tests.webapp import bots_in

DROPPED = WorkerEnd(
    state="dropped", text="Nothing to do: the list is already sorted.", question=None
)


class DroppingWorkers:
    """Workers whose every turn finds nothing to do."""

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd:
        return DROPPED

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd:
        return DROPPED


async def test_a_dropped_ticket_ends_without_a_report(tmp_path) -> None:
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    await bots.open_active_bots()
    model = ScriptedClient(completed("Heard it."))
    followed: list[Run] = []

    async def follow(run: Run) -> None:
        followed.append(run)

    tickets = TicketService(
        TicketRepository(tmp_path / "tickets.json"),
        bots,
        run_service(service, model, bots=bots),
        worker=DroppingWorkers(),
        logs=service,
        follow=follow,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        ids=lambda: "t1",
    )

    tickets.accept(bot_id=ASSISTANT_ID, title="Sort the list", task="Sort it.", mode="ask")
    for _ in range(100):
        if not tickets._worker_tasks:
            break
        await asyncio.sleep(0.01)

    assert not tickets._worker_tasks
    assert tickets.get("t1").state == "dropped"
    assert followed == []
    assert model.calls == 0
