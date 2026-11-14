"""A bot's tickets, one ticket with its worker's steps read by polling, and its answer box."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from harness.bots import BotService
from harness.secrets import SecretService
from harness.tickets.domain.models import Ticket, TicketNotAskingError
from harness.tickets.domain.prompts import SAVED_KEY_ANSWER
from harness.tickets.router.schemas import (
    TicketAnswer,
    TicketApproval,
    TicketDetail,
    TicketRow,
    TicketSecret,
)
from harness.tickets.service.ticket_service import TicketService
from harness.tools.client import ClientToolService
from harness.tools.client.models import RefusalReason
from harness.utc import utc_text


def _row(ticket: Ticket) -> TicketRow:
    return TicketRow(
        id=ticket.id,
        bot_id=ticket.bot_id,
        title=ticket.title,
        state=ticket.state,
        created_at=utc_text(ticket.created_at),
    )


class TicketRouter:
    """List a bot's tickets, read one with its worker's log, and answer its question."""

    def __init__(
        self,
        tickets: TicketService,
        secrets: SecretService,
        bots: BotService,
        client_tools: ClientToolService,
    ) -> None:
        self._tickets = tickets
        self._secrets = secrets
        self._bots = bots
        self._client_tools = client_tools
        self.router: APIRouter = APIRouter(prefix="/api/tickets", tags=["tickets"])
        self._add_reading_routes()
        self._add_person_routes()
        self._add_secret_route()
        self._add_approval_route()

    def _add_reading_routes(self) -> None:
        """Reading a bot's tickets and one with its worker's log, and answering its question."""
        self.router.add_api_route(
            "", self.list_tickets, methods=["GET"], response_model=list[TicketRow]
        )
        self.router.add_api_route(
            "/needs-you", self.list_needing_you, methods=["GET"], response_model=list[TicketRow]
        )
        self.router.add_api_route(
            "/{ticket_id}", self.get_ticket, methods=["GET"], response_model=TicketDetail
        )
        self.router.add_api_route(
            "/{ticket_id}/answer",
            self.answer_ticket,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=TicketRow,
        )

    def _add_person_routes(self) -> None:
        """Stopping a ticket, and trying a blocked or failed one again, from the Needs you page."""
        self.router.add_api_route(
            "/{ticket_id}/stop",
            self.stop_ticket,
            methods=["POST"],
            status_code=status.HTTP_204_NO_CONTENT,
        )
        self.router.add_api_route(
            "/{ticket_id}/retry",
            self.retry_ticket,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=TicketRow,
        )

    def _add_secret_route(self) -> None:
        """The key a ticket's question asks for: saved for its bot, and only its name told."""
        self.router.add_api_route(
            "/{ticket_id}/secret",
            self.save_ticket_secret,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=TicketRow,
        )

    def _add_approval_route(self) -> None:
        """The person's decision on a worker's call that asks first, taken as the bot's card is."""
        self.router.add_api_route(
            "/{ticket_id}/approve",
            self.approve_ticket,
            methods=["POST"],
            status_code=status.HTTP_202_ACCEPTED,
            response_model=TicketRow,
        )

    async def list_tickets(self, bot_id: str) -> list[TicketRow]:
        return [_row(ticket) for ticket in self._tickets.of_bot(bot_id)]

    async def list_needing_you(self) -> list[TicketRow]:
        return [_row(ticket) for ticket in self._tickets.needing_you()]

    async def get_ticket(self, ticket_id: str) -> TicketDetail:
        ticket = self._tickets.get(ticket_id)
        return TicketDetail(
            ticket=_row(ticket),
            events=list(await self._tickets.worker_events(ticket_id)),
            running=self._tickets.is_running(ticket_id),
        )

    async def answer_ticket(self, ticket_id: str, body: TicketAnswer) -> TicketRow:
        if await self._tickets.is_asking_for_key(ticket_id) or self._client_tools.answerable_calls(
            await self._tickets.asking_worker_log(ticket_id)
        ):
            raise TicketNotAskingError(ticket_id)
        self._tickets.answer(ticket_id, body.text)
        return _row(self._tickets.get(ticket_id))

    async def stop_ticket(self, ticket_id: str) -> Response:
        self._tickets.stop(ticket_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def retry_ticket(self, ticket_id: str) -> TicketRow:
        self._tickets.retry(ticket_id)
        return _row(self._tickets.get(ticket_id))

    async def save_ticket_secret(self, ticket_id: str, body: TicketSecret) -> TicketRow:
        asked = await self._tickets.asked_key(ticket_id)
        self._secrets.save(asked.name, asked.destination, body.value)
        self._bots.allow_secret(asked.bot_id, asked.name)
        self._tickets.answer(ticket_id, SAVED_KEY_ANSWER.format(name=asked.name))
        return _row(self._tickets.get(ticket_id))

    async def approve_ticket(self, ticket_id: str, body: TicketApproval) -> TicketRow:
        worker_log = await self._tickets.asking_worker_log(ticket_id)
        waiting = self._client_tools.answerable_calls(worker_log)
        if not waiting:
            raise TicketNotAskingError(ticket_id)
        raw = body.decision.model_dump()
        accepted = self._client_tools.accept_by_call_id(worker_log, waiting[-1].call_id, raw)
        if isinstance(accepted, RefusalReason):
            raise TicketNotAskingError(ticket_id)
        self._tickets.approve(ticket_id, accepted.call_id, accepted.outcome)
        return _row(self._tickets.get(ticket_id))
