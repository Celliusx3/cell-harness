"""A bot's tickets, and one ticket with its worker's steps, read by polling."""

from __future__ import annotations

from fastapi import APIRouter

from harness.tickets.models import Ticket
from harness.tickets.schemas import TicketDetail, TicketRow
from harness.tickets.service import TicketService
from harness.utc import utc_text


def _row(ticket: Ticket) -> TicketRow:
    return TicketRow(
        id=ticket.id,
        bot_id=ticket.bot_id,
        title=ticket.title,
        state=ticket.state,
        created_at=utc_text(ticket.created_at),
    )


def build_router(tickets: TicketService) -> APIRouter:
    """List a bot's tickets, and read one with its worker's log."""
    router = APIRouter(prefix="/api/tickets", tags=["tickets"])

    @router.get("", response_model=list[TicketRow])
    async def list_tickets(bot_id: str) -> list[TicketRow]:
        return [_row(ticket) for ticket in tickets.of_bot(bot_id)]

    @router.get("/{ticket_id}", response_model=TicketDetail)
    async def get_ticket(ticket_id: str) -> TicketDetail:
        ticket = tickets.get(ticket_id)
        return TicketDetail(
            ticket=_row(ticket),
            events=list(await tickets.worker_events(ticket_id)),
            running=tickets.is_running(ticket_id),
        )

    return router
