"""A call allowed for the conversation in a bot's chat runs unasked in the workers it starts."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence

import httpx
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID
from harness.llm import StreamEvent
from harness.tools import ApprovalService
from harness.tools.native.secrets import FETCH_WITH_SECRET, fetch_with_secret_tool
from harness.tools.native.tickets import TICKET_ROUTE
from tests.integration.test_web_ticket_approval import (
    ACCEPTED,
    FETCH,
    SITE,
    report,
    until_ticket,
)
from tests.integration.ticket_helpers import WORKER_START, Ticketing, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed
from tests.webapp import MODEL_CREDENTIAL

ALLOW_FOR_THE_CONVERSATION = {"kind": "approved", "scope": "conversation"}
RESEARCHER = {
    "name": "Researcher",
    "instructions": "Find sources and cite every claim.",
    "model": MODEL_CREDENTIAL,
}


def fetching_world(
    tmp_path, called: list[str], scripts: Mapping[str, Sequence[Sequence[StreamEvent]]]
) -> Ticketing:
    """Bots and workers answered by `scripts`, where `fetch_with_secret` asks first."""

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
    return ticketing_app(tmp_path, scripts, bot_tools=bot_tools, approvals=approvals)


async def until_waiting(client: httpx.AsyncClient, chat: str, call_id: str) -> None:
    """Once `chat`'s turn has ended waiting on call `call_id`."""
    for _ in range(500):
        detail = (await client.get(f"/api/conversations/{chat}")).json()
        calls = [e["call"]["id"] for e in of_type(detail["events"], "tool/call")]
        if not detail["running"] and call_id in calls:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"{chat} never waited on {call_id!r}")


async def test_a_call_allowed_for_the_conversation_in_the_chat_runs_unasked_in_its_worker(
    tmp_path,
) -> None:
    called: list[str] = []
    world = fetching_world(
        tmp_path,
        called,
        {
            WORKER_START: [
                calls_tool(FETCH_WITH_SECRET, FETCH, id="f1"),
                report(state="ready", summary="Three flights."),
                completed("Reported."),
            ],
            ASSISTANT_START: [
                calls_tool(FETCH_WITH_SECRET, FETCH, id="b1"),
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed("Done."),
            ],
        },
    )
    async with world.client as client:
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await until_waiting(client, ASSISTANT_ID, "b1")
        allowed = await client.post(
            f"/api/conversations/{ASSISTANT_ID}/calls/b1/output", json=ALLOW_FOR_THE_CONVERSATION
        )
        await once_said(client, ASSISTANT_ID, "On it.")
        await until_ticket(world, "t1", "done")

    assert allowed.status_code == 204
    assert called == ["https://api.flights.test/v1", "https://api.flights.test/v1"]


async def test_a_call_allowed_for_the_conversation_in_another_bots_chat_still_asks_in_a_worker(
    tmp_path,
) -> None:
    called: list[str] = []
    world = fetching_world(
        tmp_path,
        called,
        {
            WORKER_START: [calls_tool(FETCH_WITH_SECRET, FETCH, id="f1"), completed("Asked.")],
            ASSISTANT_START: [
                calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
                completed("On it."),
                completed("It asks first."),
            ],
            RESEARCHER["instructions"]: [
                calls_tool(FETCH_WITH_SECRET, FETCH, id="r1"),
                completed("Fetched."),
            ],
        },
    )
    async with world.client as client:
        researcher = (await client.post("/api/bots", json=RESEARCHER)).json()["id"]
        await send(client, researcher, "find a flight to Tokyo")
        await until_waiting(client, researcher, "r1")
        allowed = await client.post(
            f"/api/conversations/{researcher}/calls/r1/output", json=ALLOW_FOR_THE_CONVERSATION
        )
        granted = await once_said(client, researcher, "Fetched.")
        await send(client, ASSISTANT_ID, "find a flight to Tokyo")
        await once_said(client, ASSISTANT_ID, "On it.")
        await until_ticket(world, "t1", "needs_answer")

    assert allowed.status_code == 204
    assert [e["tool"] for e in of_type(granted, "approval/grant")] == [FETCH_WITH_SECRET]
    assert world.tickets.get("t1").state == "needs_answer"
    assert called == []
