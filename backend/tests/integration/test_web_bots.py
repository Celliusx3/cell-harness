"""Bots over HTTP: each has its instructions and one chat, and its turns answer as it."""

from __future__ import annotations

import httpx
import pytest

from harness.bots import ASSISTANT_ID, BotStore
from harness.runs.store import RunStore
from tests.integration.web_helpers import settle
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills, runtime_over
from tests.webapp import web_app

GUIDE = "GUIDE"
ASSISTANT = "You are a helpful assistant."
RESEARCHER = {"name": "Researcher", "instructions": "Find sources and cite every claim."}


@pytest.fixture
async def bots(tmp_path):
    model = ScriptedClient(completed("hello"))
    service = durable_service(tmp_path / "sessions")
    store = BotStore(tmp_path / "bots.json", service, assistant_instructions=ASSISTANT)
    runtime = runtime_over(model, guidance=GUIDE, checkpoint=service.flush)
    runs = RunStore(service, runtime, store)
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://harness.test") as client:
        yield client, model, runs


async def _say(client: httpx.AsyncClient, runs: RunStore, conversation_id: str) -> None:
    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "hi"}
    )
    assert sent.status_code == 202
    await settle(runs, conversation_id)


async def _logged_instructions(client: httpx.AsyncClient, conversation_id: str) -> list[str]:
    events = (await client.get(f"/api/conversations/{conversation_id}")).json()["events"]
    return [e["instructions"] for e in events if e["type"] == "bot/instructions"]


async def test_assistant_is_there_from_the_first_start(bots) -> None:
    client, _, _ = bots

    listed = (await client.get("/api/bots")).json()

    assert [(b["id"], b["name"], b["instructions"]) for b in listed] == [
        (ASSISTANT_ID, "Assistant", ASSISTANT)
    ]


async def test_a_new_bot_has_a_chat_that_opens_with_its_instructions(bots) -> None:
    client, _, _ = bots

    created = await client.post("/api/bots", json=RESEARCHER)

    assert created.status_code == 201
    bot = created.json()
    assert bot["name"] == "Researcher"
    assert await _logged_instructions(client, bot["id"]) == [RESEARCHER["instructions"]]
    assert [b["name"] for b in (await client.get("/api/bots")).json()] == [
        "Assistant",
        "Researcher",
    ]


async def test_a_bot_answers_with_its_instructions_first(bots) -> None:
    client, model, runs = bots
    bot_id = (await client.post("/api/bots", json=RESEARCHER)).json()["id"]

    await _say(client, runs, bot_id)

    assert model.seen[0].content == f"{RESEARCHER['instructions']} {GUIDE}"
    assert await _logged_instructions(client, bot_id) == [RESEARCHER["instructions"]]


async def test_an_edit_is_logged_once_before_the_next_turn(bots) -> None:
    client, model, runs = bots
    bot_id = (await client.post("/api/bots", json=RESEARCHER)).json()["id"]
    await _say(client, runs, bot_id)

    edited = await client.put(
        f"/api/bots/{bot_id}", json={"name": "Researcher", "instructions": "Be brief."}
    )
    await _say(client, runs, bot_id)
    await _say(client, runs, bot_id)

    assert edited.status_code == 200
    assert model.seen[0].content == f"Be brief. {GUIDE}"
    assert await _logged_instructions(client, bot_id) == [RESEARCHER["instructions"], "Be brief."]


async def test_assistant_cannot_be_deleted_and_another_bot_can(bots) -> None:
    client, _, _ = bots
    bot_id = (await client.post("/api/bots", json=RESEARCHER)).json()["id"]

    refused = await client.delete(f"/api/bots/{ASSISTANT_ID}")
    deleted = await client.delete(f"/api/bots/{bot_id}")

    assert refused.status_code == 409
    assert deleted.status_code == 204
    assert [b["id"] for b in (await client.get("/api/bots")).json()] == [ASSISTANT_ID]
    assert (await client.get(f"/api/conversations/{bot_id}")).status_code == 404


async def test_a_blank_name_or_instructions_is_refused(bots) -> None:
    client, _, _ = bots

    blank_name = await client.post("/api/bots", json={"name": "  ", "instructions": "x"})
    blank_instructions = await client.post("/api/bots", json={"name": "x", "instructions": " "})

    assert blank_name.status_code == 422
    assert blank_instructions.status_code == 422


async def test_editing_a_bot_that_does_not_exist_is_not_found(bots) -> None:
    client, _, _ = bots

    missing = await client.put("/api/bots/nope", json=RESEARCHER)

    assert missing.status_code == 404


async def test_archiving_restoring_or_deleting_a_bot_that_does_not_exist_is_not_found(
    bots,
) -> None:
    client, _, _ = bots

    assert (await client.post("/api/bots/nope/archive")).status_code == 404
    assert (await client.post("/api/bots/nope/restore")).status_code == 404
    assert (await client.delete("/api/bots/nope")).status_code == 404
