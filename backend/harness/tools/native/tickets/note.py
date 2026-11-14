"""`ticket_note`: a short fact for one of the bot's tickets, heard by its worker's next turn."""

from __future__ import annotations

from typing import Protocol

from harness.tickets.domain.models import Ticket, TicketNotFound, TicketStopped
from harness.tickets.domain.prompts import TICKET_NOTE_HEARD
from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import INVALID_ARGUMENTS, REFUSED, Failure, Ok, ToolOutcome
from harness.tools.domain.tool import Tool
from harness.tools.native.tickets.models import TicketNoteArgs

TICKET_NOTE = "ticket_note"

MAX_NOTE_WORDS = 100

_DESCRIPTION = (
    "Send one of your tickets a short fact it needs, such as a date the user gave you. The "
    "worker gets it as context for that ticket, not as a new task. A note reaches a busy worker "
    "when its current turn ends."
)


class TicketTeller(Protocol):
    """Finds a ticket, and runs its worker's next turn on a prompt."""

    def get(self, ticket_id: str) -> Ticket: ...

    def tell(self, ticket_id: str, prompt: str) -> None: ...


def ticket_note_tool(tickets: TicketTeller) -> Tool[TicketNoteArgs]:
    """The tool that sends a note to one of the calling bot's tickets."""

    async def execute(args: TicketNoteArgs, context: ToolContext) -> ToolOutcome:
        word_count = len(args.text.split())
        if word_count > MAX_NOTE_WORDS:
            return Failure(
                INVALID_ARGUMENTS, f"the note has {word_count} words; keep it to {MAX_NOTE_WORDS}"
            )
        try:
            ticket = tickets.get(args.ticket)
        except TicketNotFound:
            return Failure(INVALID_ARGUMENTS, f"no ticket has the id {args.ticket!r}")
        if ticket.bot_id != context.origin.bot_id:
            return Failure(INVALID_ARGUMENTS, f"ticket {args.ticket!r} is not one of yours")
        try:
            tickets.tell(ticket.id, TICKET_NOTE_HEARD.format(text=args.text))
        except TicketStopped:
            return Failure(REFUSED, f"ticket {ticket.id} was stopped by the user")
        return Ok(f"Sent the note to ticket {ticket.id}.")

    return Tool.from_model(
        name=TICKET_NOTE, description=_DESCRIPTION, args_model=TicketNoteArgs, execute=execute
    )
