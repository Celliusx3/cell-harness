"""A bot's tickets can be listed and each read with its worker's steps, but not written to."""

from __future__ import annotations

import json

from harness.bots import ASSISTANT_ID
from harness.tools.native.tickets import TICKET_ACCEPT
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed

ACCEPTED = json.dumps({"title": "Cheapest flights to Tokyo", "task": "Find 3 cheap flights."})
SCRIPTS = {
    WORKER_START: [completed("Three flights found.")],
    ASSISTANT_START: [
        calls_tool(TICKET_ACCEPT, ACCEPTED, id="c1"),
        completed("On it."),
        completed("Here are the flights."),
    ],
}


async def test_a_bots_tickets_are_listed_and_each_is_read_with_its_workers_steps(tmp_path) -> None:
    world = ticketing_app(tmp_path, SCRIPTS)
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")
        listed = await client.get("/api/tickets", params={"bot_id": ASSISTANT_ID})
        (row,) = listed.json()
        detail = await client.get(f"/api/tickets/{row['id']}")

    assert listed.status_code == 200
    assert (row["title"], row["state"], row["bot_id"]) == (
        "Cheapest flights to Tokyo",
        "done",
        ASSISTANT_ID,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["ticket"] == row
    assert body["running"] is False
    replies = [e["message"]["content"] for e in of_type(body["events"], "assistant/message")]
    assert replies == ["Three flights found."]


async def test_an_unknown_ticket_is_not_found(tmp_path) -> None:
    world = ticketing_app(tmp_path, SCRIPTS)
    async with world.client as client:
        missing = await client.get("/api/tickets/nope")

    assert missing.status_code == 404


async def test_a_message_to_a_workers_chat_is_refused(tmp_path) -> None:
    world = ticketing_app(tmp_path, SCRIPTS)
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")
        (ticket,) = world.tickets.of_bot(ASSISTANT_ID)
        sent = await client.post(
            f"/api/conversations/ticket-{ticket.id}/messages", json={"prompt": "hello"}
        )

    assert 400 <= sent.status_code < 500
