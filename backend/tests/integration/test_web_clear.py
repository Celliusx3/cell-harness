"""Clearing a bot's chat over HTTP: the same chat, and the model starts fresh after it."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from harness.bots import ASSISTANT_ID, BotStore
from harness.runs.store import RunStore
from tests.integration.web_helpers import assistant_chat, settle
from tests.unit.fakes import HangingClient, ScriptedClient, completed
from tests.unit.helpers import durable_service, loop_agent, no_skills, run_store
from tests.webapp import web_app


@pytest.fixture
async def assistant(tmp_path):
    model = ScriptedClient(completed("noted"))
    service = durable_service(tmp_path / "sessions")
    store = BotStore(tmp_path / "bots.json", service, assistant_instructions="ASSISTANT")
    runs = RunStore(service, loop_agent(model, checkpoint=service.flush), store)
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://harness.test") as client:
        assert (await client.get("/api/bots")).status_code == 200
        yield client, model, runs


async def _say(client: httpx.AsyncClient, runs: RunStore, prompt: str) -> None:
    sent = await client.post(f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": prompt})
    assert sent.status_code == 202
    await settle(runs, ASSISTANT_ID)


async def test_clear_starts_the_model_fresh_in_the_same_chat(assistant) -> None:
    client, model, runs = assistant
    await _say(client, runs, "my name is Ana")

    cleared = await client.post(f"/api/conversations/{ASSISTANT_ID}/clear")
    await _say(client, runs, "what is my name?")

    assert cleared.status_code == 204
    sent = " ".join(str(message.content) for message in model.seen)
    assert "what is my name?" in sent
    assert "Ana" not in sent
    chat = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()
    assert "chat/cleared" in [event["type"] for event in chat["events"]]


async def test_clearing_an_unknown_chat_is_a_404(assistant) -> None:
    client, _, _ = assistant

    assert (await client.post("/api/conversations/nope/clear")).status_code == 404


async def test_clearing_a_running_chat_stops_its_turn(tmp_path) -> None:
    service = durable_service(tmp_path / "sessions")
    runs = run_store(service, HangingClient("thinking"))
    app = web_app(tmp_path, service, runs, skills=no_skills())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        cid = await assistant_chat(c, "go")
        run = runs.active(cid)
        while not any(event.type == "assistant/chunk" for event in run.session.events()):
            await asyncio.sleep(0.01)

        cleared = await c.post(f"/api/conversations/{cid}/clear")
        chat = (await c.get(f"/api/conversations/{cid}")).json()

    assert cleared.status_code == 204
    assert runs.active(cid) is None
    assert chat["running"] is False
    assert chat["events"][-1]["type"] == "chat/cleared"
