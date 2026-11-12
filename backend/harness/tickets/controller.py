"""A bot's tickets, one ticket with its worker's steps read by polling, and its answer box."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from harness.tickets.models import Ticket
from harness.tickets.schemas import TicketAnswer, TicketDetail, TicketRow
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

    @router.get("/needs-you", response_model=list[TicketRow])
    async def list_needing_you() -> list[TicketRow]:
        return [_row(ticket) for ticket in tickets.needing_you()]

    @router.get("/{ticket_id}", response_model=TicketDetail)
    async def get_ticket(ticket_id: str) -> TicketDetail:
        ticket = tickets.get(ticket_id)
        return TicketDetail(
            ticket=_row(ticket),
            events=list(await tickets.worker_events(ticket_id)),
            running=tickets.is_running(ticket_id),
        )

    @router.post(
        "/{ticket_id}/answer", status_code=status.HTTP_202_ACCEPTED, response_model=TicketRow
    )
    async def answer_ticket(ticket_id: str, body: TicketAnswer) -> TicketRow:
        tickets.answer(ticket_id, body.text)
        return _row(tickets.get(ticket_id))

    _person_routes(router, tickets)
    return router


def _person_routes(router: APIRouter, tickets: TicketService) -> None:
    """Stopping a ticket, and trying a blocked or failed one again, from the Needs you page."""

    @router.post("/{ticket_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
    async def stop_ticket(ticket_id: str) -> Response:
        tickets.stop(ticket_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/{ticket_id}/retry", status_code=status.HTTP_202_ACCEPTED, response_model=TicketRow
    )
    async def retry_ticket(ticket_id: str) -> TicketRow:
        tickets.retry(ticket_id)
        return _row(tickets.get(ticket_id))
