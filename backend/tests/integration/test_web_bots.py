"""Bots over HTTP: each has its instructions and one chat, and its turns answer as it."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from harness.app_events import AppEventService
from harness.bots import (
    ASSISTANT_ID,
    BUILDER_ID,
    MENTION_TURN_ORDER,
    BotRepository,
    BotService,
    GroupService,
)
from harness.bots.domain.models import DEFAULT_MAX_WORKERS
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.runs.service.run_service import RunService
from tests.integration.web_helpers import settle
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills, runtime_over
from tests.webapp import MODEL_CREDENTIAL, a_model_saved_in, web_app

GUIDE = "GUIDE"
ASSISTANT = "You are a helpful assistant."
RESEARCHER = {
    "name": "Researcher",
    "instructions": "Find sources and cite every claim.",
    "model": MODEL_CREDENTIAL,
}


@pytest.fixture
async def bots(tmp_path):
    model = ScriptedClient(completed("hello"))
    service = durable_service(tmp_path / "sessions")
    app_events = AppEventService()
    store = BotService(
        BotRepository(tmp_path / "bots.json"),
        service,
        assistant_instructions=ASSISTANT,
        app_events=app_events,
    )
    runtime = runtime_over(model, guidance=GUIDE, checkpoint=service.flush)
    runs = RunService(
        service,
        runtime,
        store,
        GroupService(store, service, MENTION_TURN_ORDER),
        app_events=app_events,
    )
    app = web_app(
        tmp_path, service, runs, skills=no_skills(), bots=store, secrets=a_model_saved_in(tmp_path)
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://harness.test") as client:
        yield client, model, runs


async def _say(client: httpx.AsyncClient, runs: RunService, conversation_id: str) -> None:
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
        (ASSISTANT_ID, "Assistant", ASSISTANT),
        (BUILDER_ID, "Bot builder", BUILDER_INSTRUCTIONS),
    ]


async def test_listing_the_bots_saves_no_chat(bots, tmp_path: Path) -> None:
    client, _, _ = bots

    listed = await client.get("/api/bots")

    assert listed.status_code == 200, listed.text
    assert [b["id"] for b in listed.json()] == [ASSISTANT_ID, BUILDER_ID]
    assert sorted(path.name for path in (tmp_path / "sessions").glob("*.jsonl")) == []


async def test_a_new_bot_has_a_chat_that_opens_with_its_instructions(bots) -> None:
    client, _, _ = bots

    created = await client.post("/api/bots", json=RESEARCHER)

    assert created.status_code == 201
    bot = created.json()
    assert bot["name"] == "Researcher"
    assert await _logged_instructions(client, bot["id"]) == [RESEARCHER["instructions"]]
    assert [b["name"] for b in (await client.get("/api/bots")).json()] == [
        "Assistant",
        "Bot builder",
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
        f"/api/bots/{bot_id}",
        json={
            "name": "Researcher",
            "instructions": "Be brief.",
            "model": None,
            "max_workers": DEFAULT_MAX_WORKERS,
        },
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
    assert [b["id"] for b in (await client.get("/api/bots")).json()] == [ASSISTANT_ID, BUILDER_ID]
    assert (await client.get(f"/api/conversations/{bot_id}")).status_code == 404


async def test_a_blank_name_or_instructions_is_refused(bots) -> None:
    client, _, _ = bots

    blank_name = await client.post("/api/bots", json={**RESEARCHER, "name": "  "})
    blank_instructions = await client.post("/api/bots", json={**RESEARCHER, "instructions": " "})

    assert blank_name.status_code == 422
    assert blank_instructions.status_code == 422


async def test_editing_a_bot_that_does_not_exist_is_not_found(bots) -> None:
    client, _, _ = bots

    edit = {
        "name": "Researcher",
        "instructions": "Cite.",
        "model": None,
        "max_workers": DEFAULT_MAX_WORKERS,
    }
    missing = await client.put("/api/bots/nope", json=edit)

    assert missing.status_code == 404


async def test_archiving_restoring_or_deleting_a_bot_that_does_not_exist_is_not_found(
    bots,
) -> None:
    client, _, _ = bots

    assert (await client.post("/api/bots/nope/archive")).status_code == 404
    assert (await client.post("/api/bots/nope/restore")).status_code == 404
    assert (await client.delete("/api/bots/nope")).status_code == 404
