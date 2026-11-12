"""`ticket_accept`: one task handed to a worker, whose result arrives later on its own."""

from __future__ import annotations

from typing import Protocol

from harness.tickets.models import Ticket
from harness.tools.models.context import ToolContext
from harness.tools.models.decision import ApprovalMode
from harness.tools.models.outcome import Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.tickets.models import TicketAcceptArgs

TICKET_ACCEPT = "ticket_accept"

_DESCRIPTION = (
    "Start a ticket: hand one task to a worker that does it in the background, in its own chat "
    "and folder. Call it when a request needs real work. The call returns once the worker "
    "starts, and the worker's result arrives later as a new message that wakes you. Do not call "
    "it again to check on a ticket."
)


class TicketStarter(Protocol):
    """Saves a ticket for `bot_id` and starts its worker in `mode`."""

    def accept(self, *, bot_id: str, title: str, task: str, mode: ApprovalMode) -> Ticket: ...


def ticket_accept_tool(tickets: TicketStarter) -> Tool[TicketAcceptArgs]:
    """The tool that starts a ticket for the calling bot, and returns once its worker starts."""

    async def execute(args: TicketAcceptArgs, context: ToolContext) -> ToolOutcome:
        ticket = tickets.accept(
            bot_id=context.origin.bot_id,
            title=args.title,
            task=args.task,
            mode=context.origin.mode,
        )
        return Ok(
            f"Started ticket {ticket.id}, titled {ticket.title}. Its result will arrive as a new "
            "message; do not call again to check on it."
        )

    return Tool.from_model(
        name=TICKET_ACCEPT, description=_DESCRIPTION, args_model=TicketAcceptArgs, execute=execute
    )
