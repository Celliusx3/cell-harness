"""A ticket's state from its reports, and a ticket whose worker breaks or is shut down."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from harness.bots import ASSISTANT_ID
from harness.tickets.domain.models import (
    ReportState,
    StoppedTicketError,
    Ticket,
    TicketState,
    ticket_state,
)
from harness.tickets.repository.ticket_repository import TicketRepository
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import WorkerEnd
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import (
    FirstTurnOnly,
    durable_service,
    heard_nowhere,
    no_bots,
    run_service,
)


def tickets_on(tmp_path, worker) -> TicketService:
    service = durable_service(tmp_path / "sessions")
    bots = no_bots(service)
    return TicketService(
        TicketRepository(tmp_path / "tickets.json"),
        bots,
        run_service(service, ScriptedClient([]), bots=bots),
        worker=FirstTurnOnly(worker),
        logs=service,
        follow=heard_nowhere,
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        ids=lambda: "t1",
    )


async def until_ended(tickets: TicketService, bot_id: str) -> Ticket:
    for _ in range(200):
        (ticket,) = tickets.of_bot(bot_id)
        if ticket.state != "working":
            return ticket
        await asyncio.sleep(0.01)
    raise AssertionError("the ticket never ended")


async def test_a_worker_that_breaks_fails_its_ticket_and_a_gone_bot_hears_nothing(
    tmp_path,
) -> None:
    async def broken(ticket: Ticket) -> WorkerEnd:
        raise RuntimeError("kaboom")

    tickets = tickets_on(tmp_path, broken)
    tickets.accept(bot_id=ASSISTANT_ID, title="T", task="do it", mode="auto")

    assert (await until_ended(tickets, ASSISTANT_ID)).state == "failed"
    await tickets.aclose()


async def test_shutting_down_cancels_a_running_worker_and_leaves_its_ticket_working(
    tmp_path,
) -> None:
    started = asyncio.Event()

    async def hangs(ticket: Ticket) -> WorkerEnd:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    tickets = tickets_on(tmp_path, hangs)
    tickets.accept(bot_id=ASSISTANT_ID, title="T", task="do it", mode="auto")
    await started.wait()
    await tickets.aclose()

    assert [t.state for t in tickets.of_bot(ASSISTANT_ID)] == ["working"]


@pytest.mark.parametrize(
    ("state", "question", "expected"),
    [
        ("ready", None, "done"),
        ("blocked", "Which one?", "needs_answer"),
        ("waiting", "Which one?", "needs_answer"),
        ("blocked", None, "blocked"),
        ("waiting", None, "waiting"),
        ("failed", None, "failed"),
        ("dropped", None, "dropped"),
    ],
)
def test_a_report_sets_its_tickets_state(
    state: ReportState, question: str | None, expected: TicketState
) -> None:
    assert ticket_state(state, question) == expected


def test_a_progress_report_never_sets_a_tickets_state() -> None:
    with pytest.raises(ValueError):
        ticket_state("progress", None)


async def test_a_worker_that_has_written_nothing_has_no_steps(tmp_path) -> None:
    async def hangs(ticket: Ticket) -> WorkerEnd:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    tickets = tickets_on(tmp_path, hangs)
    ticket = tickets.accept(bot_id=ASSISTANT_ID, title="T", task="do it", mode="auto")
    await asyncio.sleep(0)

    assert await tickets.worker_events(ticket.id) == ()
    assert tickets.is_running(ticket.id)
    await tickets.aclose()


async def test_stopping_a_ticket_cancels_its_worker_and_it_takes_nothing_more(tmp_path) -> None:
    started = asyncio.Event()

    async def hangs(ticket: Ticket) -> WorkerEnd:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    tickets = tickets_on(tmp_path, hangs)
    ticket = tickets.accept(bot_id=ASSISTANT_ID, title="T", task="do it", mode="auto")
    await started.wait()
    tickets.stop(ticket.id)
    await asyncio.sleep(0)

    assert not tickets.is_running(ticket.id)
    assert tickets.get(ticket.id).state == "stopped"
    with pytest.raises(StoppedTicketError):
        tickets.tell(ticket.id, "go on")
    with pytest.raises(StoppedTicketError):
        tickets.stop(ticket.id)
    await tickets.aclose()


async def test_a_ticket_whose_bot_is_gone_fails_without_running(tmp_path) -> None:
    ran: list[str] = []

    async def runs(ticket: Ticket) -> WorkerEnd:
        ran.append(ticket.id)
        raise AssertionError("unreachable")

    tickets = tickets_on(tmp_path, runs)
    tickets.accept(bot_id="gone", title="T", task="do it", mode="auto")

    assert (await until_ended(tickets, "gone")).state == "failed"
    assert ran == []
    await tickets.aclose()
