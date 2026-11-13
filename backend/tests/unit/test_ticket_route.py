"""`ticket_route` does each item on its own, and a refused item never stops the others."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from harness.tickets.domain.models import Ticket, TicketNotFound, TicketStopped
from harness.tools import ApprovalMode, Ok
from harness.tools.native.tickets import ticket_route_tool
from tests.unit.helpers import context_for

CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def ticket(ticket_id: str, bot_id: str = "s", state: str = "done") -> Ticket:
    return Ticket(id=ticket_id, bot_id=bot_id, title="T", task="t", state=state, created_at=CREATED)


@dataclass
class Router:
    tickets: dict[str, Ticket] = field(
        default_factory=lambda: {
            "t1": ticket("t1"),
            "t2": ticket("t2", bot_id="other"),
            "t3": ticket("t3", state="stopped"),
        }
    )
    told: list[str] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)

    def accept(self, *, bot_id: str, title: str, task: str, mode: ApprovalMode) -> Ticket:
        return ticket("t9").model_copy(update={"title": title})

    def get(self, ticket_id: str) -> Ticket:
        if ticket_id not in self.tickets:
            raise TicketNotFound(ticket_id)
        return self.tickets[ticket_id]

    def tell(self, ticket_id: str, prompt: str) -> None:
        if self.get(ticket_id).state == "stopped":
            raise TicketStopped(ticket_id)
        self.told.append(ticket_id)

    def stop(self, ticket_id: str) -> None:
        if self.get(ticket_id).state == "stopped":
            raise TicketStopped(ticket_id)
        self.stopped.append(ticket_id)


async def route(router: Router, *items: dict) -> str:
    outcome = await ticket_route_tool(router).invoke(
        json.dumps({"items": list(items)}), context=context_for()
    )
    assert isinstance(outcome, Ok)
    return outcome.text


async def test_each_kind_is_done_and_answered_on_its_own_numbered_line() -> None:
    router = Router()
    text = await route(
        router,
        {"kind": "accept", "title": "Flights", "task": "Find flights."},
        {"kind": "attach", "ticket": "t1", "text": "business class too"},
        {"kind": "stop", "ticket": "t1"},
        {"kind": "ignore", "reason": "thanks"},
    )

    assert text.splitlines() == [
        "1. accepted ticket t9, titled Flights",
        "2. attached to ticket t1",
        "3. stopped ticket t1",
        "4. ignored: thanks",
    ]
    assert (router.told, router.stopped) == (["t1"], ["t1"])


async def test_a_refused_item_does_not_stop_the_items_after_it() -> None:
    router = Router()
    text = await route(
        router,
        {"kind": "attach", "ticket": "nope", "text": "x"},
        {"kind": "attach", "ticket": "t2", "text": "x"},
        {"kind": "attach", "ticket": "t3", "text": "x"},
        {"kind": "stop", "ticket": "t3"},
        {"kind": "attach", "ticket": "t1", "text": "x"},
    )

    lines = text.splitlines()
    assert all(line.split(". ", 1)[1].startswith("refused: ") for line in lines[:4])
    assert "stopped by the user" in lines[2]
    assert lines[4] == "5. attached to ticket t1"
