"""`ticket_route`: what to do with the user's message, one item for each request in it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from harness.tickets.domain.models import Ticket, TicketNotFound, TicketStopped
from harness.tickets.domain.prompts import TICKET_FOLLOWUP_HEARD
from harness.tools.models.context import ToolContext
from harness.tools.models.decision import ApprovalMode
from harness.tools.models.outcome import Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.tickets.models import (
    AcceptItem,
    AttachItem,
    IgnoreItem,
    RouteItem,
    StopItem,
    TicketRouteArgs,
)

TICKET_ROUTE = "ticket_route"

_DESCRIPTION = (
    "Decide what to do with the user's message, in one call with one item for each request in "
    "it. accept hands new work to a worker on a new ticket. attach sends the message to one of "
    "your tickets that it points at, and resumes that ticket if it ended. stop ends a ticket the "
    "user asked to stop. ignore records that the message asks for no work. Each item is done on "
    "its own, and a refused item does not stop the others."
)


class TicketRouter(Protocol):
    """Starts, finds, tells and stops tickets."""

    def accept(self, *, bot_id: str, title: str, task: str, mode: ApprovalMode) -> Ticket: ...

    def get(self, ticket_id: str) -> Ticket: ...

    def tell(self, ticket_id: str, prompt: str) -> None: ...

    def stop(self, ticket_id: str) -> None: ...


class Refused(Exception):
    """Why one item was not done, as its line says."""


def ticket_route_tool(tickets: TicketRouter) -> Tool[TicketRouteArgs]:
    """The tool that does each item in turn, and answers with one numbered line for each."""

    async def execute(args: TicketRouteArgs, context: ToolContext) -> ToolOutcome:
        lines = [
            f"{number}. {_line(tickets, item, context)}"
            for number, item in enumerate(args.items, start=1)
        ]
        return Ok("\n".join(lines))

    return Tool.from_model(
        name=TICKET_ROUTE, description=_DESCRIPTION, args_model=TicketRouteArgs, execute=execute
    )


def _line(tickets: TicketRouter, item: RouteItem, context: ToolContext) -> str:
    """What became of `item`, or why it was refused."""
    try:
        return _done(tickets, item, context)
    except Refused as refused:
        return f"refused: {refused}"


def _done(tickets: TicketRouter, item: RouteItem, context: ToolContext) -> str:
    """Do `item`, and say what was done; `Refused` when it cannot be."""
    bot_id = context.origin.bot_id
    match item:
        case AcceptItem(title=title, task=task):
            ticket = tickets.accept(bot_id=bot_id, title=title, task=task, mode=context.origin.mode)
            return f"accepted ticket {ticket.id}, titled {ticket.title}"
        case AttachItem(ticket=ticket_id, text=text):
            ticket = _own(tickets, ticket_id, bot_id)
            _unless_stopped(
                lambda: tickets.tell(ticket.id, TICKET_FOLLOWUP_HEARD.format(text=text))
            )
            return f"attached to ticket {ticket.id}"
        case StopItem(ticket=ticket_id):
            ticket = _own(tickets, ticket_id, bot_id)
            _unless_stopped(lambda: tickets.stop(ticket.id))
            return f"stopped ticket {ticket.id}"
        case IgnoreItem(reason=reason):
            return f"ignored: {reason}"


def _own(tickets: TicketRouter, ticket_id: str, bot_id: str) -> Ticket:
    """The calling bot's ticket `ticket_id`; `Refused` when it is unknown or another bot's."""
    try:
        ticket = tickets.get(ticket_id)
    except TicketNotFound:
        raise Refused(f"no ticket has the id {ticket_id}") from None
    if ticket.bot_id != bot_id:
        raise Refused(f"ticket {ticket_id} is not one of yours")
    return ticket


def _unless_stopped(action: Callable[[], None]) -> None:
    """Run `action`; `Refused` when its ticket was stopped by the user."""
    try:
        action()
    except TicketStopped as stopped:
        raise Refused(f"ticket {stopped} was stopped by the user") from None
