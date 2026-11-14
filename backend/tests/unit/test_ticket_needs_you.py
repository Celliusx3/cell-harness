"""Tickets that wait for a person, retrying one, and the app event every change publishes."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from harness.app_events import TicketsChangedAppEvent
from harness.bots import ASSISTANT_ID
from harness.tickets.domain.models import Ticket, TicketsFile, UnretryableTicketError
from harness.tickets.repository.ticket_repository import TicketRepository
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import WorkerEnd
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import FirstTurnOnly, durable_service, heard_nowhere, no_bots, run_service


async def never(ticket: Ticket) -> WorkerEnd:
    raise AssertionError("no worker runs here")


def ticket(ticket_id: str, state: str, day: int) -> Ticket:
    return Ticket(
        id=ticket_id,
        bot_id=ASSISTANT_ID,
        title=ticket_id,
        task="t",
        state=state,
        created_at=datetime(2026, 1, day, tzinfo=UTC),
    )


def tickets_holding(tmp_path, *held: Ticket) -> TicketService:
    repository = TicketRepository(tmp_path / "tickets.json")
    repository.write(TicketsFile(tickets=held))
    service = durable_service(tmp_path / "sessions")
    bots = no_bots(service)
    return TicketService(
        repository,
        bots,
        run_service(service, ScriptedClient([]), bots=bots),
        worker=FirstTurnOnly(never),
        logs=service,
        follow=heard_nowhere,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        ids=lambda: "new",
    )


def test_only_tickets_that_wait_for_a_person_are_listed_oldest_first(tmp_path) -> None:
    tickets = tickets_holding(
        tmp_path,
        ticket("late", "failed", 3),
        ticket("done", "done", 1),
        ticket("asks", "needs_answer", 2),
        ticket("stuck", "blocked", 1),
        ticket("busy", "working", 1),
    )

    assert [t.id for t in tickets.needing_you()] == ["stuck", "asks", "late"]


def test_only_a_blocked_or_failed_ticket_is_retried(tmp_path) -> None:
    tickets = tickets_holding(tmp_path, ticket("asks", "needs_answer", 1))

    with pytest.raises(UnretryableTicketError):
        tickets.retry("asks")


async def test_a_change_of_state_tells_the_app_that_tickets_changed(tmp_path) -> None:
    tickets = tickets_holding(tmp_path, ticket("t1", "failed", 1))
    events = tickets._runs.app_events.subscribe()
    heard = asyncio.create_task(asyncio.wait_for(anext(events), timeout=1.0))
    await asyncio.sleep(0)

    tickets.stop("t1")

    assert await heard == TicketsChangedAppEvent()
    await events.aclose()
