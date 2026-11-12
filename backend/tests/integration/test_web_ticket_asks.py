"""A worker's question chooses its card: an option is tapped, a key is saved and never logged."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.tools.native.secrets import FETCH_WITH_SECRET, fetch_with_secret_tool
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed

ACCEPTED = json.dumps(
    {"items": [{"kind": "accept", "title": "Flights to Tokyo", "task": "Find a flight."}]}
)
KEY = "sk-never-in-a-log-4242"
SITE = {"origin": "https://api.flights.test", "auth": "bearer"}


def report(**fields: object) -> list:
    return calls_tool(TICKET_REPORT, json.dumps(fields), id=f"r-{fields['state']}")


def bot_script(*after: list) -> list:
    return [
        calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
        completed("On it."),
        completed("The ticket waits for your answer."),
        *after,
    ]


async def until_state(world, state: str) -> None:
    for _ in range(500):
        tickets = world.tickets.of_bot(ASSISTANT_ID)
        if tickets and tickets[0].state == state and not world.tickets.is_running(tickets[0].id):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"the ticket never reached {state!r}")


def answered_with(world, text: str) -> bool:
    second_turn = world.model.seen_by[WORKER_START][2]
    heard = f"The user answered your question: {text}"
    return any(isinstance(m, UserMessage) and m.content == heard for m in second_turn)


async def test_a_tapped_option_reaches_the_worker(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(
                    state="blocked",
                    summary="Two kinds of flight.",
                    question="Direct or 1-stop?",
                    ask="choice",
                    options=["Direct", "1-stop"],
                ),
                completed("Asked."),
                report(state="ready", summary="A 1-stop flight."),
                completed("Reported."),
            ],
            ASSISTANT_START: bot_script(completed("Here is the flight.")),
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        asked = await once_said(client, ASSISTANT_ID, "The ticket waits for your answer.")
        await until_state(world, "needs_answer")
        tapped = await client.post("/api/tickets/t1/answer", json={"text": "1-stop"})
        await once_said(client, ASSISTANT_ID, "Here is the flight.")

    (shown,) = of_type(asked, "ticket/report")
    assert (shown["report"]["ask"], shown["report"]["options"]) == ("choice", ["Direct", "1-stop"])
    assert tapped.status_code == 202
    assert answered_with(world, "1-stop")


async def test_a_saved_key_reaches_the_worker_by_name_only(tmp_path) -> None:
    sent: list[str] = []

    def api(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers["authorization"])
        return httpx.Response(200, json={"flights": 3})

    fetch = json.dumps(
        {"name": "flights_key", "url": "https://api.flights.test/v1", "method": "GET"}
    )
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(
                    state="blocked",
                    summary="Needs the flights API key.",
                    question="Paste your flights API key.",
                    ask="secret",
                    secret_name="flights_key",
                    secret_destination=SITE,
                ),
                completed("Asked."),
                calls_tool(FETCH_WITH_SECRET, fetch, id="f1"),
                report(state="ready", summary="Three flights."),
                completed("Reported."),
            ],
            ASSISTANT_START: bot_script(completed("Three flights found.")),
        },
        bot_tools=lambda bots, secrets: (
            fetch_with_secret_tool(secrets, bots, httpx.MockTransport(api)),
        ),
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "The ticket waits for your answer.")
        await until_state(world, "needs_answer")
        saved = await client.post("/api/tickets/t1/secret", json={"value": KEY})
        again = await client.post("/api/tickets/t1/secret", json={"value": KEY})
        await once_said(client, ASSISTANT_ID, "Three flights found.")
        await until_state(world, "done")

    assert saved.status_code == 202
    assert again.status_code == 409
    assert answered_with(world, "Saved the key flights_key.")
    assert sent == [f"Bearer {KEY}"]
    assert not any(KEY in path.read_text() for path in logs_under(tmp_path))


async def test_a_key_is_refused_for_a_question_that_asks_for_text(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(state="blocked", summary="Needs a date.", question="Which day?"),
                completed("Asked."),
            ],
            ASSISTANT_START: bot_script(),
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "The ticket waits for your answer.")
        await until_state(world, "needs_answer")
        refused = await client.post("/api/tickets/t1/secret", json={"value": KEY})

    assert refused.status_code == 409


async def test_a_typed_answer_is_refused_for_a_question_that_asks_for_a_key(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(
                    state="blocked",
                    summary="Needs the flights API key.",
                    question="Paste your flights API key.",
                    ask="secret",
                    secret_name="flights_key",
                    secret_destination=SITE,
                ),
                completed("Asked."),
            ],
            ASSISTANT_START: bot_script(),
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "The ticket waits for your answer.")
        await until_state(world, "needs_answer")
        typed = await client.post("/api/tickets/t1/answer", json={"text": KEY})

    assert typed.status_code == 409
    assert world.tickets.get("t1").state == "needs_answer"
    assert not any(KEY in path.read_text() for path in logs_under(tmp_path))


def logs_under(root: Path) -> list[Path]:
    """Every session log and the tickets file: whatever a model or a page could read back."""
    return [*root.rglob("*.jsonl"), root / "tickets.json"]
