"""A bot starts a ticket: a worker does it in the background, and its result wakes the bot."""

from __future__ import annotations

import json

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.tickets.domain.prompts import TICKET_TURN_FAILED
from harness.tools.native.tickets import TICKET_ROUTE
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


async def test_a_ticket_runs_in_the_background_and_its_result_wakes_the_bot(tmp_path) -> None:
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
        log = await once_said(client, ASSISTANT_ID, "Here are the flights.")

    assert of_type(log, "tool/result")[0]["error"] is None
    assert [e["bot_id"] for e in of_type(log, "turn/start")] == [ASSISTANT_ID] * 2
    (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
    assert (ticket.title, ticket.state) == ("Cheapest flights to Tokyo", "done")
    assert [e["report"] for e in of_type(log, "ticket/report")] == [
        {
            "ticket_id": ticket.id,
            "title": ticket.title,
            "state": "ready",
            "text": "Three flights found.",
            "question": None,
            "ask": "text",
            "options": None,
            "secret_name": None,
            "approval_call_id": None,
            "approval_tool": None,
        }
    ]
    worker = await world.worker_logs.read(f"ticket-{ticket.id}")
    assert any(
        isinstance(m, UserMessage) and m.content.startswith("Find 3 cheap flights.")
        for m in world.model.seen_by[WORKER_START][0]
    )
    assert worker.events()
    woken = world.model.seen_by[ASSISTANT_START][2]
    assert any(isinstance(m, UserMessage) and "Three flights found." in m.content for m in woken)


async def test_a_worker_that_fails_ends_its_ticket_as_failed(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [[]],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed("The ticket failed."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        log = await once_said(client, ASSISTANT_ID, "The ticket failed.")

    (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
    assert ticket.state == "failed"
    (report,) = of_type(log, "ticket/report")
    assert report["report"]["text"] == TICKET_TURN_FAILED.format(
        reason="stream ended without a terminal event"
    )
