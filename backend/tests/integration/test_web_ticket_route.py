"""The bot routes each message: accept starts tickets, attach resumes one, stop ends one."""

from __future__ import annotations

import asyncio
import json

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.tools.native.tickets import TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed

FLIGHTS = {"kind": "accept", "title": "Flights to Tokyo", "task": "Find 3 cheap flights."}
HOTELS = {"kind": "accept", "title": "Hotels in Tokyo", "task": "Find 3 cheap hotels."}


def route(*items: dict, call_id: str) -> list:
    """The bot's step that calls ticket_route with `items`."""
    return calls_tool(TICKET_ROUTE, json.dumps({"items": list(items)}), id=call_id)


async def until_idle(world) -> None:
    """Wait until no ticket's worker is running."""
    for _ in range(500):
        tickets = world.tickets.of_bot(ASSISTANT_ID)
        if tickets and not any(world.tickets.is_running(t.id) for t in tickets):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("a worker never went idle")


def result_text(log: list[dict], call_id: str) -> str:
    """The text of the tool result for `call_id`."""
    (result,) = [e for e in of_type(log, "tool/result") if e["message"]["tool_call_id"] == call_id]
    return result["message"]["content"][0]["text"]


async def test_one_message_with_two_requests_starts_two_tickets(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [completed("Found them.")],
            ASSISTANT_START: [
                route(FLIGHTS, HOTELS, call_id="r1"),
                completed("Started flights and hotels."),
                completed("One is done."),
                completed("Both are done."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights and hotels in Tokyo")
        log = await once_said(client, ASSISTANT_ID, "Both are done.")

    tickets = world.tickets.of_bot(ASSISTANT_ID)
    assert [(t.id, t.title) for t in tickets] == [
        ("t1", "Flights to Tokyo"),
        ("t2", "Hotels in Tokyo"),
    ]
    text = result_text(log, "r1")
    assert "accepted ticket t1" in text and "accepted ticket t2" in text


async def test_thanks_is_ignored_and_starts_no_ticket(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            ASSISTANT_START: [
                route({"kind": "ignore", "reason": "thanks, no work"}, call_id="r1"),
                completed("You're welcome."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "thanks")
        log = await once_said(client, ASSISTANT_ID, "You're welcome.")

    assert world.tickets.of_bot(ASSISTANT_ID) == ()
    assert "ignored" in result_text(log, "r1")


async def test_attach_resumes_a_done_ticket_with_the_users_message(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [completed("Three flights found."), completed("Business class too.")],
            ASSISTANT_START: [
                route(FLIGHTS, call_id="r1"),
                completed("On it."),
                completed("Here are the flights."),
                route(
                    {"kind": "attach", "ticket": "t1", "text": "check business class too"},
                    call_id="r2",
                ),
                completed("Checking business class."),
                completed("Business class is there too."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")
        await until_idle(world)
        await send(client, ASSISTANT_ID, "for the Tokyo flights, check business class too")
        log = await once_said(client, ASSISTANT_ID, "Business class is there too.")

    assert "attached to ticket t1" in result_text(log, "r2")
    assert any(
        isinstance(m, UserMessage)
        and m.content == "The user wrote this about your ticket: check business class too"
        for m in world.model.seen_by[WORKER_START][1]
    )


async def test_a_stopped_ticket_refuses_an_attach_without_stopping_the_batch(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [completed("Three flights found."), completed("Hotels found.")],
            ASSISTANT_START: [
                route(FLIGHTS, call_id="r1"),
                completed("On it."),
                completed("Here are the flights."),
                route({"kind": "stop", "ticket": "t1"}, call_id="r2"),
                completed("Stopped."),
                route(
                    {"kind": "attach", "ticket": "t1", "text": "go on"},
                    HOTELS,
                    call_id="r3",
                ),
                completed("Started hotels."),
                completed("Hotels done."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find flights to Tokyo")
        await once_said(client, ASSISTANT_ID, "Here are the flights.")
        await until_idle(world)
        await send(client, ASSISTANT_ID, "stop the flights")
        await once_said(client, ASSISTANT_ID, "Stopped.")
        await send(client, ASSISTANT_ID, "go on with flights, and find hotels")
        log = await once_said(client, ASSISTANT_ID, "Hotels done.")

    states = {t.id: t.state for t in world.tickets.of_bot(ASSISTANT_ID)}
    assert states == {"t1": "stopped", "t2": "done"}
    text = result_text(log, "r3")
    assert "refused" in text and "stopped" in text and "accepted ticket t2" in text
