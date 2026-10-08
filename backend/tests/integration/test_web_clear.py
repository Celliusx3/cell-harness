"""Clearing a bot's chat over HTTP: the same chat, and the model starts fresh after it."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from harness.bots import ASSISTANT_ID, BotStore
from harness.llm.messages import Message
from harness.llm.stream import StreamEvent
from harness.runs.service import RunStore
from harness.tools.definition import ToolSpec
from tests.integration.web_helpers import assistant_chat, settle
from tests.unit.fakes import HangingClient, ScriptedClient, SteppedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_store, runtime_over
from tests.webapp import web_app


@pytest.fixture
async def assistant(tmp_path):
    model = ScriptedClient(completed("noted"))
    service = durable_service(tmp_path / "sessions")
    store = BotStore(tmp_path / "bots.json", service, assistant_instructions="ASSISTANT")
    runs = RunStore(service, runtime_over(model, checkpoint=service.flush), store)
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


class HoldsFirstCall(SteppedClient):
    """Holds the first call it is asked until it is cancelled, then answers in order."""

    def __init__(self, *replies: str) -> None:
        super().__init__(*(completed(reply) for reply in replies))
        self._held = False

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        if not self._held:
            self._held = True
            await asyncio.Event().wait()
        async for event in super().stream_completion(messages, model, tools=tools):
            yield event


async def test_a_message_sent_while_a_clear_stops_the_turn_lands_after_the_clear(tmp_path) -> None:
    service = durable_service(tmp_path / "sessions")
    model = HoldsFirstCall("fresh answer")
    runs = run_store(service, model)
    app = web_app(tmp_path, service, runs, skills=no_skills())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        cid = await assistant_chat(c, "the secret word is PELICAN")
        run = runs.active(cid)
        while not any(event.type == "step/start" for event in run.session.events()):
            await asyncio.sleep(0.01)

        clearing = asyncio.create_task(c.post(f"/api/conversations/{cid}/clear"))
        while not run._inner.done():
            await asyncio.sleep(0)
        sent = await c.post(f"/api/conversations/{cid}/messages", json={"prompt": "after"})
        assert (await clearing).status_code == 204
        for _ in range(300):
            if runs.active(cid) is None and model.calls == 1:
                break
            await asyncio.sleep(0.01)
        chat = (await c.get(f"/api/conversations/{cid}")).json()

    assert sent.status_code == 202
    stored = (tmp_path / "sessions" / f"{cid}.jsonl").read_text(encoding="utf-8")
    assert "PELICAN" not in stored
    assert chat["events"][0]["type"] == "chat/cleared"
    prompts = [e["message"]["content"] for e in chat["events"] if e["type"] == "user/message"]
    assert prompts == ["after"]
    assert "PELICAN" not in " ".join(str(message.content) for message in model.seen)


async def test_a_clear_that_cannot_wipe_the_chat_says_so(tmp_path, monkeypatch) -> None:
    service = durable_service(tmp_path / "sessions")
    runs = run_store(service, ScriptedClient(completed("noted")))
    app = web_app(tmp_path, service, runs, skills=no_skills())

    async def broken(session_id: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(service, "clear", broken)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        cid = await assistant_chat(c, "hello")
        await settle(runs, cid)
        cleared = await c.post(f"/api/conversations/{cid}/clear")

    assert cleared.status_code == 500
