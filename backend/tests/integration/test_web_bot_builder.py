"""Bot builder over HTTP: a worker interviews the person, then the builder makes the bot."""

from __future__ import annotations

import asyncio
import json

import httpx

from harness.bots import BUILDER_ID
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.tools import ApprovalService
from harness.tools.native.bots import BOT_CREATE, bot_create_tool
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from harness.web.runtime import DEFAULT_TOOLS
from harness.web.tickets_wiring import WORKER_TOOLS
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import of_type, once_said, send
from tests.unit.fakes import calls_tool, completed
from tests.webapp import MODEL_CREDENTIAL

ACCEPTED = json.dumps(
    {
        "items": [
            {
                "kind": "accept",
                "title": "A bot for reading notes",
                "task": "Ask the user what the bot is for and which model it answers on.",
            }
        ]
    }
)
QUESTION = "Which model should it answer on?"
SUMMARY = f"Name: Reader. Instructions: You quiz me on my reading notes. Model: {MODEL_CREDENTIAL}."
READER = json.dumps(
    {
        "name": "Reader",
        "instructions": "You quiz me on my reading notes.",
        "model": MODEL_CREDENTIAL,
    }
)
APPROVE = f"/api/conversations/{BUILDER_ID}/calls/call_reader/output"


def report(**fields: str) -> list:
    return calls_tool(TICKET_REPORT, json.dumps(fields), id=f"r-{fields['state']}")


async def until_ticket(world, state: str) -> None:
    for _ in range(500):
        tickets = world.tickets.of_bot(BUILDER_ID)
        if tickets and tickets[0].state == state and not world.tickets.is_running(tickets[0].id):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"the ticket never reached {state!r}")


async def once_waiting(client: httpx.AsyncClient) -> list[dict]:
    for _ in range(500):
        detail = (await client.get(f"/api/conversations/{BUILDER_ID}")).json()
        ends = [e["reason"] for e in of_type(detail["events"], "turn/end")]
        if not detail["running"] and ends and ends[-1] == "pending":
            return detail["events"]
        await asyncio.sleep(0.01)
    raise AssertionError("the builder never waited for an approval")


async def test_a_worker_interviews_the_person_and_the_builder_makes_the_bot(tmp_path) -> None:
    approvals = ApprovalService(
        frozenset({BOT_CREATE}), frozenset, tmp_path / "approvals.json", default_mode="ask"
    )
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(state="blocked", summary="Needs the model.", question=QUESTION),
                completed("Asked."),
                report(state="ready", summary=SUMMARY),
                completed("Reported."),
            ],
            BUILDER_INSTRUCTIONS: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("I started a ticket to design your bot."),
                completed("The ticket waits for your answer."),
                calls_tool(BOT_CREATE, READER, id="call_reader"),
                completed("Reader is under Bots."),
            ],
        },
        bot_tools=lambda bots, secrets: (bot_create_tool(bots, secrets),),
        approvals=approvals,
    )
    async with world.client as client:
        await send(client, BUILDER_ID, "I want a bot for my reading notes")
        await once_said(client, BUILDER_ID, "The ticket waits for your answer.")
        await until_ticket(world, "needs_answer")
        (ticket,) = world.tickets.of_bot(BUILDER_ID)
        answered = await client.post(
            f"/api/tickets/{ticket.id}/answer", json={"text": MODEL_CREDENTIAL}
        )
        log = await once_waiting(client)
        approved = await client.post(APPROVE, json={"kind": "approved", "scope": "once"})
        await once_said(client, BUILDER_ID, "Reader is under Bots.")
        listed = (await client.get("/api/bots")).json()

    assert "ticket_route" in BUILDER_INSTRUCTIONS and "ask_user" not in BUILDER_INSTRUCTIONS
    assert [e["name"] for e in of_type(log, "bot/instructions")] == ["Bot builder"]
    assert answered.status_code == 202
    assert [e["report"]["state"] for e in of_type(log, "ticket/report")] == ["blocked", "ready"]
    assert approved.status_code == 204
    assert [b["name"] for b in listed] == ["Assistant", "Bot builder", "Reader"]
    assert BOT_CREATE in DEFAULT_TOOLS and BOT_CREATE not in WORKER_TOOLS
