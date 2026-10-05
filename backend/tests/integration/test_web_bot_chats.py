"""Every chat is a bot's chat: an id that is no bot's is refused on every route."""

from __future__ import annotations

import httpx
import pytest

from harness.bots import ASSISTANT_ID, BotStore
from harness.llm.messages import UserMessage
from harness.session.models import UserMessageEvent
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills
from tests.webapp import web_app

ROUTES = (
    ("GET", "/api/conversations/{id}", None),
    ("GET", "/api/conversations/{id}/events", None),
    ("POST", "/api/conversations/{id}/messages", {"prompt": "hi"}),
    ("POST", "/api/conversations/{id}/clear", None),
    ("POST", "/api/conversations/{id}/compact", None),
    ("DELETE", "/api/conversations/{id}/run", None),
    ("POST", "/api/conversations/{id}/calls/call_1/output", {}),
)


@pytest.fixture
async def chats(tmp_path):
    service, runs = build(tmp_path, ScriptedClient(completed("hello")))
    bots = BotStore(tmp_path / "bots.json", service, assistant_instructions="ASSISTANT")
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=bots)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        assert (await client.get("/api/bots")).status_code == 200
        yield client, service


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_an_id_that_is_no_bots_is_a_404(chats, method, path, body) -> None:
    client, _ = chats

    response = await client.request(method, path.format(id="nope"), json=body)

    assert response.status_code == 404


async def test_an_old_chat_on_disk_that_no_bot_owns_is_a_404(chats) -> None:
    client, service = chats
    old = await service.create("an-old-chat")
    old.append(UserMessageEvent(turn=0, message=UserMessage(content="from before")))
    await service.flush(old)

    assert (await client.get("/api/conversations/an-old-chat")).status_code == 404


async def test_there_is_no_list_of_chats_and_no_way_to_start_another(chats) -> None:
    client, _ = chats

    listed = await client.get("/api/conversations")
    started = await client.post("/api/conversations", json={"prompt": "hi"})

    assert listed.status_code in (404, 405)
    assert started.status_code in (404, 405)


async def test_a_bots_chat_still_answers(chats) -> None:
    client, _ = chats

    assert (await client.get(f"/api/conversations/{ASSISTANT_ID}")).status_code == 200
