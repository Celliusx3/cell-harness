"""A worker reports in a fixed form: the ticket takes its state, and only an end wakes the bot."""

from __future__ import annotations

import json

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
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


async def test_a_blocked_report_with_a_question_wakes_the_bot_with_it(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(state="blocked", summary="Two airlines need a choice.", question=QUESTION),
                completed("Asked."),
            ],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed(QUESTION),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        log = await once_said(client, ASSISTANT_ID, QUESTION)

    (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
    assert ticket.state == "needs_answer"
    assert [e["report"] for e in of_type(log, "ticket/report")] == [
        {
            "ticket_id": ticket.id,
            "title": ticket.title,
            "state": "blocked",
            "text": "Two airlines need a choice.",
            "question": QUESTION,
        }
    ]
    woken = world.model.seen_by[ASSISTANT_START][2]
    assert any(isinstance(m, UserMessage) and QUESTION in m.content for m in woken)


async def test_progress_wakes_nobody_and_the_ready_report_ends_the_ticket(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(state="progress", summary="Checked two airlines."),
                report(state="ready", summary="Three flights found."),
                completed("Reported."),
            ],
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

    (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
    assert ticket.state == "done"
    assert [e["bot_id"] for e in of_type(log, "turn/start")] == [ASSISTANT_ID] * 2
    assert [(e["report"]["state"], e["report"]["text"]) for e in of_type(log, "ticket/report")] == [
        ("ready", "Three flights found.")
    ]
