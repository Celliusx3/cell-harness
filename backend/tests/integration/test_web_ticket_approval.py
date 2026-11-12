"""A worker's call that asks first becomes its ticket's question, approved or denied in the app."""

from __future__ import annotations

import asyncio
import json

import httpx
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID
from harness.llm import ToolMessage
from harness.prompts import DENIED_RESULT
from harness.secrets import Destination
from harness.tools import ApprovalService
from harness.tools.native.secrets import FETCH_WITH_SECRET, fetch_with_secret_tool
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed

ACCEPTED = json.dumps(
    {"items": [{"kind": "accept", "title": "Flights to Tokyo", "task": "Find a flight."}]}
)
FETCH = json.dumps({"name": "flights_key", "url": "https://api.flights.test/v1", "method": "GET"})
SITE = Destination(origin="https://api.flights.test", auth="bearer")


def report(**fields: str) -> list:
    return calls_tool(TICKET_REPORT, json.dumps(fields), id=f"r-{fields['state']}")


async def until_state(world, state: str) -> None:
    for _ in range(500):
        tickets = world.tickets.of_bot(ASSISTANT_ID)
        if tickets and tickets[0].state == state and not world.tickets.is_running(tickets[0].id):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"the ticket never reached {state!r}")


def asking_world(
    tmp_path,
    called: list[str],
    after: list[list],
    bot_replies: list[list] | None = None,
):
    """A worker whose first call, `fetch_with_secret`, asks first; then the steps in `after`."""

    def api(request: httpx.Request) -> httpx.Response:
        called.append(str(request.url))
        return httpx.Response(200, json={"flights": 3})

    def bot_tools(bots, secrets):
        secrets.save("flights_key", SITE, SecretStr("sk-flights-4242"))
        bots.allow_secret(ASSISTANT_ID, "flights_key")
        return (fetch_with_secret_tool(secrets, bots, httpx.MockTransport(api)),)

    approvals = ApprovalService(
        frozenset({FETCH_WITH_SECRET}), frozenset, tmp_path / "approvals.json", default_mode="ask"
    )
    return ticketing_app(
        tmp_path,
        {
            WORKER_START: [calls_tool(FETCH_WITH_SECRET, FETCH, id="f1"), *after],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                *(bot_replies or [completed("Done.")]),
            ],
        },
        bot_tools=bot_tools,
        approvals=approvals,
    )


async def test_an_allowed_call_runs_and_the_worker_finishes(tmp_path) -> None:
    called: list[str] = []
    world = asking_world(
        tmp_path,
        called,
        [report(state="ready", summary="Three flights."), completed("Reported.")],
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "On it.")
        await until_state(world, "needs_answer")
        log = await bot_log(client)
        allowed = await client.post(
            "/api/tickets/t1/approve", json={"decision": {"kind": "approved", "scope": "once"}}
        )
        again = await client.post(
            "/api/tickets/t1/approve", json={"decision": {"kind": "approved", "scope": "once"}}
        )
        await once_said(client, ASSISTANT_ID, "Done.")
        await until_state(world, "done")

    (asked,) = of_type(log, "ticket/report")
    assert asked["report"]["state"] == "blocked"
    assert asked["report"]["ask"] == "approval"
    assert asked["report"]["question"] == "Allow fetch_with_secret?"
    assert (asked["report"]["approval_call_id"], asked["report"]["approval_tool"]) == (
        "f1",
        FETCH_WITH_SECRET,
    )
    assert allowed.status_code == 202
    assert again.status_code == 409
    assert called == ["https://api.flights.test/v1"]


async def test_a_denied_call_is_heard_by_the_worker_which_reports(tmp_path) -> None:
    called: list[str] = []
    world = asking_world(
        tmp_path,
        called,
        [report(state="failed", summary="The user denied the call."), completed("Reported.")],
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "On it.")
        await until_state(world, "needs_answer")
        denied = await client.post("/api/tickets/t1/approve", json={"decision": {"kind": "denied"}})
        await once_said(client, ASSISTANT_ID, "Done.")
        await until_state(world, "failed")

    assert denied.status_code == 202
    assert called == []
    after_the_answer = world.model.seen_by[WORKER_START][1]
    assert any(
        isinstance(m, ToolMessage) and DENIED_RESULT in str(m.content) for m in after_the_answer
    )


async def test_an_approval_is_refused_for_a_question_that_asks_for_text(tmp_path) -> None:
    world = ticketing_app(
        tmp_path,
        {
            WORKER_START: [
                report(state="blocked", summary="Needs a date.", question="Which day?"),
                completed("Asked."),
            ],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed("The ticket waits for your answer."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "The ticket waits for your answer.")
        await until_state(world, "needs_answer")
        refused = await client.post(
            "/api/tickets/t1/approve", json={"decision": {"kind": "approved", "scope": "once"}}
        )

    assert refused.status_code == 409


async def test_a_typed_answer_is_refused_for_a_question_that_asks_for_approval(tmp_path) -> None:
    called: list[str] = []
    world = asking_world(tmp_path, called, [completed("Reported.")])
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "On it.")
        await until_state(world, "needs_answer")
        typed = await client.post("/api/tickets/t1/answer", json={"text": "yes go ahead"})

    assert typed.status_code == 409
    assert world.tickets.get("t1").state == "needs_answer"
    assert called == []


async def bot_log(client) -> list[dict]:
    return (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()["events"]


async def test_an_approval_is_logged_in_the_bots_chat_without_waking_it(tmp_path) -> None:
    called: list[str] = []
    world = asking_world(
        tmp_path,
        called,
        [
            calls_tool(FETCH_WITH_SECRET, FETCH, id="f2"),
            report(state="ready", summary="Three flights."),
            completed("Reported."),
        ],
        bot_replies=[completed("Here are the flights.")],
    )
    allow = {"decision": {"kind": "approved", "scope": "once"}}
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "On it.")
        await until_state(world, "needs_answer")
        first = await bot_log(client)
        await client.post("/api/tickets/t1/approve", json=allow)
        await until_state(world, "needs_answer")
        second = await bot_log(client)
        await client.post("/api/tickets/t1/approve", json=allow)
        done = await once_said(client, ASSISTANT_ID, "Here are the flights.")

    asks = [e["report"]["ask"] for e in of_type(done, "ticket/report")]
    assert asks == ["approval", "approval", "text"]
    assert [e["report"]["approval_call_id"] for e in of_type(second, "ticket/report")] == [
        "f1",
        "f2",
    ]
    assert len(of_type(first, "turn/start")) == len(of_type(second, "turn/start")) == 1
    assert len(of_type(done, "turn/start")) == 2
    assert len(called) == 2
