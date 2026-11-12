"""`ticket_note` sends a short fact to one of the bot's own tickets, and refuses anything else."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from harness.tickets.models import Ticket, TicketNotFound
from harness.tools import INVALID_ARGUMENTS, Failure, Ok
from harness.tools.native.tickets import ticket_note_tool
from tests.unit.helpers import context_for

TICKET = Ticket(
    id="t1",
    bot_id="s",
    title="T",
    task="do it",
    state="waiting",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@dataclass
class Told:
    prompts: list[tuple[str, str]] = field(default_factory=list)

    def get(self, ticket_id: str) -> Ticket:
        if ticket_id != TICKET.id:
            raise TicketNotFound(ticket_id)
        return TICKET

    def tell(self, ticket_id: str, prompt: str) -> None:
        self.prompts.append((ticket_id, prompt))


async def note(told: Told, ticket: str, text: str, *, bot_id: str = "s") -> object:
    arguments = json.dumps({"ticket": ticket, "text": text})
    return await ticket_note_tool(told).invoke(arguments, context=context_for(bot_id=bot_id))


async def test_a_note_reaches_the_bots_own_ticket() -> None:
    told = Told()

    assert await note(told, "t1", "Travel on the 12th.") == Ok("Sent the note to ticket t1.")
    assert [ticket for ticket, _ in told.prompts] == ["t1"]


async def test_a_long_note_an_unknown_ticket_and_another_bots_ticket_are_refused() -> None:
    told = Told()
    refused = [
        await note(told, "t1", "word " * 101),
        await note(told, "t9", "Travel on the 12th."),
        await note(told, "t1", "Travel on the 12th.", bot_id="other"),
    ]

    assert all(isinstance(r, Failure) and r.code == INVALID_ARGUMENTS for r in refused)
    assert told.prompts == []
