"""A bot answers on the model it is tied to, and one with no model refuses with one line."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

from harness.bots import ASSISTANT_ID
from harness.config.sections import LLMSettings
from harness.llm import Image
from harness.llm.adapters import OpenAIClient
from harness.llm.adapters.openai import client as adapter_module
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.web.bot_models import CredentialModels
from tests.integration.web_helpers import settle
from tests.unit.helpers import durable_service, no_skills
from tests.webapp import bots_in, secrets_in, web_app

PICK_A_MODEL = "Pick a model for this bot in Edit bot."
PAGE = "http://127.0.0.1:4887"
PROVIDER = "https://api.provider.example/v1"
SETUP_CREDENTIAL = {
    "name": "first_model",
    "details": {"kind": "llm", "base_url": PROVIDER, "model": "provider-model"},
    "value": "sk-provider-key-1234",
    "bot_ids": [ASSISTANT_ID],
}
RESEARCHER = {"name": "Researcher", "instructions": "Find sources."}


@dataclass
class FakeProvider:
    """An OpenAI-compatible endpoint that answers every request with one short reply."""

    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        delta = json.dumps({"choices": [{"delta": {"content": "hello"}}]})
        return httpx.Response(200, content=f"data: {delta}\n\ndata: [DONE]\n\n".encode())


def no_image(image: Image) -> bytes | None:
    return None


@dataclass(frozen=True)
class App:
    client: httpx.AsyncClient
    runs: RunService
    provider: FakeProvider


@pytest.fixture
async def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    secrets = secrets_in(tmp_path)
    base = LLMSettings(_env_file=None, model="unused", vision=False, base_url=PROVIDER)
    models = CredentialModels(secrets, bots, base, lambda s: OpenAIClient(s, read_image=no_image))
    runtime = Runtime(models=models, images=None, checkpoint=service.flush)
    runs = RunService(service, runtime, bots)
    asgi = web_app(tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=secrets)
    transport = httpx.ASGITransport(app=asgi, client=("127.0.0.1", 50000))
    client = httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1:4886", headers={"origin": PAGE}
    )
    provider = FakeProvider()
    real = httpx.AsyncClient
    monkeypatch.setattr(
        adapter_module.httpx,
        "AsyncClient",
        lambda **kwargs: real(transport=httpx.MockTransport(provider), **kwargs),
    )
    async with client:
        yield App(client, runs, provider)


async def _say(app: App, conversation_id: str) -> list[dict]:
    sent = await app.client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "hi"}
    )
    assert sent.status_code == 202, sent.text
    await settle(app.runs, conversation_id)
    return (await app.client.get(f"/api/conversations/{conversation_id}")).json()["events"]


def _last_chunk(events: list[dict]) -> dict:
    return [event for event in events if event["type"] == "assistant/chunk"][-1]["chunk"]


async def test_setup_ties_assistant_and_a_bot_with_no_model_refuses(app: App) -> None:
    saved = await app.client.post("/api/credentials", json=SETUP_CREDENTIAL)
    assert saved.status_code == 201, saved.text

    await _say(app, ASSISTANT_ID)
    assert len(app.provider.requests) == 1

    researcher = (await app.client.post("/api/bots", json=RESEARCHER)).json()["id"]
    events = await _say(app, researcher)
    assert len(app.provider.requests) == 1
    assert _last_chunk(events) == {"kind": "failed", "reason": PICK_A_MODEL, "code": None}
    assert events[-1]["type"] == "turn/end"

    removed = await app.client.delete("/api/credentials/first_model")
    assert removed.status_code == 204, removed.text
    events = await _say(app, ASSISTANT_ID)
    assert len(app.provider.requests) == 1
    assert _last_chunk(events)["reason"] == PICK_A_MODEL
