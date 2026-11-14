"""A ticket's question is answered in its own box, and the answer reaches only its worker."""

from __future__ import annotations

import asyncio
import json

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.tools.native.tickets import TICKET_NOTE, TICKET_REPORT, TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed

ACCEPTED = json.dumps(
    {
        "items": [
            {
                "kind": "accept",
                "title": "Cheapest flights to Tokyo",
                "task": "Find 3 cheap flights.",
            }
        ]
    }
)
QUESTION = "Direct flights only, or are 1-stop flights OK?"


def report(**fields: str) -> list:
    """The worker's step that calls ticket_report with `fields`."""
    return calls_tool(TICKET_REPORT, json.dumps(fields), id=f"r-{fields['state']}")


async def until_state(world, state: str) -> None:
    """Wait until the bot's only ticket is in `state` and its worker is idle."""
    for _ in range(500):
        tickets = world.tickets.of_bot(ASSISTANT_ID)
        if tickets and tickets[0].state == state and not world.tickets.is_running(tickets[0].id):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"the ticket never reached {state!r}")


async def test_an_answer_goes_to_the_worker_and_its_next_report_wakes_the_bot(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(state="blocked", summary="Two airlines need a choice.", question=QUESTION),
                report(state="ready", summary="Three 1-stop flights found."),
            ],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed("The ticket waits for your answer."),
                completed("Here are the flights."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "The ticket waits for your answer.")
        await until_state(world, "needs_answer")
        (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
        answered = await client.post(
            f"/api/tickets/{ticket.id}/answer", json={"text": "1-stop is fine"}
        )
        log = await once_said(client, ASSISTANT_ID, "Here are the flights.")
        await until_state(world, "done")

    assert answered.status_code == 202
    worker_second_turn = world.model.seen_by[WORKER_START][1]
    assert any(
        isinstance(m, UserMessage)
        and m.content == "The user answered your question: 1-stop is fine"
        for m in worker_second_turn
    )
    assert [e["report"]["state"] for e in of_type(log, "ticket/report")] == ["blocked", "ready"]


async def test_an_answer_to_a_ticket_that_asked_nothing_is_refused(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [completed("Three flights found.")],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed("Here are the flights."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")
        await until_state(world, "done")
        (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
        answered = await client.post(f"/api/tickets/{ticket.id}/answer", json={"text": "hi"})

    assert answered.status_code == 409


async def test_a_note_from_the_bot_reaches_the_worker_as_context(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(state="waiting", summary="Waiting for the travel dates."),
                report(state="ready", summary="Three flights on the 12th."),
            ],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                calls_tool(
                    TICKET_NOTE,
                    json.dumps({"ticket": "t1", "text": "Travel on the 12th."}),
                    id="n1",
                ),
                completed("Sent the dates."),
                completed("Here are the flights."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")

    worker_second_turn = world.model.seen_by[WORKER_START][1]
    assert any(
        isinstance(m, UserMessage)
        and m.content
        == "A note from the orchestrator. It is context for this ticket, not a new task: "
        "Travel on the 12th."
        for m in worker_second_turn
    )
