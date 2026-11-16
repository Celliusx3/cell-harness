"""Where a ticket's report is heard: by its bot, in the chat the ticket came from."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from harness.bots import BotNotFound, BotService
from harness.groups import NotAChatMemberError
from harness.runs.service.run import Run
from harness.runs.service.run_service import RunService
from harness.session.domain.models import TicketReport, TicketReportEvent
from harness.session.repository.session_repository import SessionNotFoundError
from harness.tickets.domain.models import Ticket, ticket_chat_id

logger = logging.getLogger("harness.tickets")

Follow = Callable[[Run], Awaitable[None]]


@dataclass(frozen=True)
class ReportDelivery:
    """Opens the turn in which a ticket's bot hears its report, then has `follow` follow it."""

    bots: BotService
    runs: RunService
    follow: Follow

    async def deliver(self, ticket: Ticket, report: TicketReport) -> None:
        """The turn `report` opens for `ticket`'s bot once its chat is free; an approval, logged."""
        try:
            chat_id = self._chat_heard_in(ticket)
            if report.ask == "approval":
                await self.runs.log_when_free(
                    chat_id, lambda turn: TicketReportEvent(turn=turn, report=report)
                )
                return
            run = await self.runs.hear_when_free(chat_id, report, speaker_id=ticket.bot_id)
        except (BotNotFound, SessionNotFoundError, NotAChatMemberError) as err:
            logger.warning("ticket report dropped, nobody is left to hear it: %s", err)
            return
        await self.follow(run)

    def _chat_heard_in(self, ticket: Ticket) -> str:
        """The ticket's chat while its bot answers there; else its bot's own chat, warned."""
        chat_id = ticket_chat_id(ticket, chat_of=self.bots.chat_of)
        if self.runs.groups.is_member(chat_id, ticket.bot_id):
            return chat_id
        logger.warning(
            "ticket %s's bot %s no longer answers in chat %s; its report goes to its own chat",
            ticket.id,
            ticket.bot_id,
            chat_id,
        )
        return self.bots.chat_of(ticket.bot_id)
