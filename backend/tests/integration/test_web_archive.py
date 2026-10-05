"""Archiving a bot: hidden with its chat, restored whole, or deleted for good."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from harness.bots import ASSISTANT_ID, BotStore
from harness.session.models import TurnEnd, UserMessageEvent
from tests.integration.web_helpers import build, settle
from tests.unit.fakes import HangingClient, ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills
from tests.webapp import web_app

RESEARCHER = {"name": "Researcher", "instructions": "Find sources and cite every claim."}


@pytest.fixture
async def bots(tmp_path):
    service, runs = build(tmp_path, ScriptedClient(completed("hello")))
    store = BotStore(tmp_path / "bots.json", service, assistant_instructions="ASSISTANT")
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        bot_id = (await client.post("/api/bots", json=RESEARCHER)).json()["id"]
        sent = await client.post(f"/api/conversations/{bot_id}/messages", json={"prompt": "hi"})
        assert sent.status_code == 202
        await settle(runs, bot_id)
        yield client, bot_id, tmp_path


def _ids(bots: list[dict]) -> list[str]:
    return [bot["id"] for bot in bots]


async def test_archiving_a_bot_hides_it_and_its_chat(bots) -> None:
    client, bot_id, _ = bots

    archived = await client.post(f"/api/bots/{bot_id}/archive")

    assert archived.status_code == 204
    assert bot_id not in _ids((await client.get("/api/bots")).json())
    assert _ids((await client.get("/api/bots/archived")).json()) == [bot_id]
    assert (await client.get(f"/api/conversations/{bot_id}")).status_code == 404


async def test_restoring_brings_the_bot_back_with_its_chat(bots) -> None:
    client, bot_id, _ = bots
    await client.post(f"/api/bots/{bot_id}/archive")

    restored = await client.post(f"/api/bots/{bot_id}/restore")
    chat = await client.get(f"/api/conversations/{bot_id}")

    assert restored.status_code == 204
    assert bot_id in _ids((await client.get("/api/bots")).json())
    assert (await client.get("/api/bots/archived")).json() == []
    prompts = [
        e["message"]["content"] for e in chat.json()["events"] if e["type"] == "user/message"
    ]
    assert prompts == ["hi"]


async def test_deleting_removes_the_bot_and_its_chat_for_good(bots) -> None:
    client, bot_id, tmp_path = bots
    await client.post(f"/api/bots/{bot_id}/archive")

    deleted = await client.delete(f"/api/bots/{bot_id}")

    assert deleted.status_code == 204
    assert bot_id not in _ids((await client.get("/api/bots")).json())
    assert (await client.get("/api/bots/archived")).json() == []
    assert not (tmp_path / "sessions" / f"{bot_id}.jsonl").exists()


async def test_assistant_can_be_neither_archived_nor_deleted(bots) -> None:
    client, _, _ = bots

    assert (await client.post(f"/api/bots/{ASSISTANT_ID}/archive")).status_code == 409
    assert (await client.delete(f"/api/bots/{ASSISTANT_ID}")).status_code == 409
    assert ASSISTANT_ID in _ids((await client.get("/api/bots")).json())


async def test_archiving_a_bot_stops_its_running_turn_and_keeps_its_chat_whole(tmp_path) -> None:
    service, runs = build(tmp_path, HangingClient("thinking"))
    store = BotStore(tmp_path / "bots.json", service, assistant_instructions="ASSISTANT")
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        bot_id = (await c.post("/api/bots", json=RESEARCHER)).json()["id"]
        await c.post(f"/api/conversations/{bot_id}/messages", json={"prompt": "go"})
        run = runs.active(bot_id)
        while not any(event.type == "assistant/chunk" for event in run.session.events()):
            await asyncio.sleep(0.01)

        archived = await c.post(f"/api/bots/{bot_id}/archive")

    stored = await durable_service(tmp_path / "sessions").read(bot_id)
    assert archived.status_code == 204
    assert runs.active(bot_id) is None
    assert [e.message.content for e in stored.events() if isinstance(e, UserMessageEvent)] == ["go"]
    assert stored.events()[-1] == TurnEnd(turn=0, reason="cancelled")


async def test_a_refused_archive_leaves_assistant_s_turn_running(tmp_path) -> None:
    service, runs = build(tmp_path, HangingClient("thinking"))
    app = web_app(tmp_path, service, runs, skills=no_skills())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await c.post(f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": "go"})

        refused = await c.post(f"/api/bots/{ASSISTANT_ID}/archive")

    assert refused.status_code == 409
    assert runs.active(ASSISTANT_ID) is not None
    await runs.stop(ASSISTANT_ID)
