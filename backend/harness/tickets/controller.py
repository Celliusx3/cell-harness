"""A bot's tickets, one ticket with its worker's steps read by polling, and its answer box."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from harness.bots import BotService
from harness.secrets import SecretService
from harness.tickets.models import Ticket, TicketNotAsking
from harness.tickets.prompts import SAVED_KEY_ANSWER
from harness.tickets.schemas import TicketAnswer, TicketDetail, TicketRow, TicketSecret
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


def build_router(tickets: TicketService, secrets: SecretService, bots: BotService) -> APIRouter:
    """List a bot's tickets, read one with its worker's log, and answer its question."""
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
        if await tickets.asks_for_key(ticket_id):
            raise TicketNotAsking(ticket_id)
        tickets.answer(ticket_id, body.text)
        return _row(tickets.get(ticket_id))

    _person_routes(router, tickets)
    _secret_route(router, tickets, secrets, bots)
    return router


def _secret_route(
    router: APIRouter, tickets: TicketService, secrets: SecretService, bots: BotService
) -> None:
    """The key a ticket's question asks for: saved for its bot, and only its name told."""

    @router.post(
        "/{ticket_id}/secret", status_code=status.HTTP_202_ACCEPTED, response_model=TicketRow
    )
    async def save_ticket_secret(ticket_id: str, body: TicketSecret) -> TicketRow:
        asked = await tickets.asked_key(ticket_id)
        secrets.save(asked.name, asked.destination, body.value)
        bots.allow_secret(asked.bot_id, asked.name)
        tickets.answer(ticket_id, SAVED_KEY_ANSWER.format(name=asked.name))
        return _row(tickets.get(ticket_id))


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
