"""Tickets that wait for a person are listed across bots, and each can be stopped or retried."""

from __future__ import annotations

import asyncio
import json

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, once_said, send
from tests.unit.fakes import calls_tool, completed

FLIGHTS = {"kind": "accept", "title": "Flights to Tokyo", "task": "Find 3 cheap flights."}
RETRY = (
    "The user asked you to try this ticket again. Check what you already did before you "
    "repeat anything."
)


def route(*items: dict, call_id: str) -> list:
    return calls_tool(TICKET_ROUTE, json.dumps({"items": list(items)}), id=call_id)


def report(**fields: str) -> list:
    return calls_tool(TICKET_REPORT, json.dumps(fields), id=f"r-{fields['state']}")


async def until_state(world, state: str) -> None:
    for _ in range(500):
        tickets = world.tickets.of_bot(ASSISTANT_ID)
        if tickets and tickets[0].state == state and not world.tickets.is_running(tickets[0].id):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"the ticket never reached {state!r}")


def failing_then_ready() -> dict:
    return {
        WORKER_START: [
            report(state="failed", summary="The airline site was down."),
            completed("Reported."),
            report(state="ready", summary="Three flights found."),
            completed("Reported."),
        ],
        ASSISTANT_START: [
            route(FLIGHTS, call_id="r1"),
            completed("On it."),
            completed("The flights ticket failed."),
            completed("Here are the flights."),
        ],
    }


async def test_a_failed_ticket_is_listed_and_retrying_it_runs_its_worker_again(tmp_path) -> None:
    world = ticketing_app(tmp_path, failing_then_ready())
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "The flights ticket failed.")
        await until_state(world, "failed")
        listed = (await client.get("/api/tickets/needs-you")).json()
        retried = await client.post("/api/tickets/t1/retry")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")
        await until_state(world, "done")
        after = (await client.get("/api/tickets/needs-you")).json()

    assert [(t["id"], t["state"], t["bot_id"]) for t in listed] == [("t1", "failed", ASSISTANT_ID)]
    assert retried.status_code == 202
    assert any(
        isinstance(m, UserMessage) and m.content == RETRY
        for m in world.model.seen_by[WORKER_START][2]
    )
    assert after == []


async def test_a_ticket_in_the_list_can_be_stopped_and_then_leaves_it(tmp_path) -> None:
    world = ticketing_app(tmp_path, failing_then_ready())
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "The flights ticket failed.")
        await until_state(world, "failed")
        stopped = await client.post("/api/tickets/t1/stop")
        again = await client.post("/api/tickets/t1/stop")
        listed = (await client.get("/api/tickets/needs-you")).json()

    assert stopped.status_code == 204
    assert again.status_code == 409
    assert listed == []
    assert world.tickets.get("t1").state == "stopped"


async def test_only_a_blocked_or_failed_ticket_can_be_retried(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [completed("Three flights found.")],
            ASSISTANT_START: [
                route(FLIGHTS, call_id="r1"),
                completed("On it."),
                completed("Here are the flights."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")
        await until_state(world, "done")
        retried = await client.post("/api/tickets/t1/retry")
        missing = await client.post("/api/tickets/nope/retry")

    assert retried.status_code == 409
    assert missing.status_code == 404
