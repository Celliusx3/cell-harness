"""Bot builder over HTTP: a built-in bot whose chat ends in a bot the person approved."""

from __future__ import annotations

import httpx

from harness.bots import BotService
from harness.tools.approval import ApprovalGate
from harness.tools.client import ClientToolService
from harness.tools.native.bots import BOT_CREATE, bot_create_tool
from harness.web.runtime import CLIENT_TOOLS
from tests.integration.web_helpers import settle
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import web_app

BUILDER = "builder"
READER = '{"name": "Reader", "instructions": "You quiz me on my reading notes."}'
ANSWER = "/api/conversations/builder/calls/call_reader/output"


async def test_the_builder_makes_the_bot_its_chat_drafted_once_it_is_allowed(tmp_path) -> None:
    gate = ApprovalGate(frozenset({BOT_CREATE}), frozenset, tmp_path / "approvals.json")
    client_tools = ClientToolService(CLIENT_TOOLS, gate)
    service = durable_service(tmp_path / "sessions")
    bots = BotService(tmp_path / "bots.json", service, assistant_instructions="ASSISTANT")
    model = SteppedClient(
        calls_tool(BOT_CREATE, READER, id="call_reader"), completed("Reader is under Bots.")
    )
    runs = run_service(
        service, model, bot_create_tool(bots), *client_tools.definitions(), gate=gate, bots=bots
    )
    app = web_app(
        tmp_path, service, runs, skills=no_skills(), client_tools=client_tools, gate=gate, bots=bots
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://harness.test") as client:
        sent = await client.post(
            f"/api/conversations/{BUILDER}/messages",
            json={"prompt": "I want a bot for my reading notes"},
        )
        assert sent.status_code == 202
        await settle(runs, BUILDER)

        detail = (await client.get(f"/api/conversations/{BUILDER}")).json()
        logged = [e for e in detail["events"] if e["type"] == "bot/instructions"]
        assert [e["name"] for e in logged] == ["Bot builder"]
        assert model.seen_per_call[0][0].content.startswith(logged[0]["instructions"])
        assert [e["reason"] for e in detail["events"] if e["type"] == "turn/end"] == ["pending"]

        answered = await client.post(ANSWER, json={"kind": "approved", "scope": "once"})
        assert answered.status_code == 204
        await settle(runs, BUILDER)

        listed = (await client.get("/api/bots")).json()
        assert [b["name"] for b in listed] == ["Assistant", "Bot builder", "Reader"]
