"""A bot answers on the model picked for it in Edit bot, and one with no model refuses."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

from harness.bots import ASSISTANT_ID, BUILDER_ID, BotService
from harness.config.sections import LLMSettings
from harness.llm import Image
from harness.llm.adapters import OpenAIClient
from harness.llm.adapters.openai import client as adapter_module
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.secrets import SecretService
from harness.tools import Failure, Ok
from harness.tools.native.bots import bot_create_tool
from harness.web.bot_models import CredentialModels
from tests.integration.web_helpers import settle
from tests.unit.helpers import context_for, durable_service, no_skills
from tests.webapp import bots_in, secrets_in, web_app

PICK_A_MODEL = "Pick a model for this bot in Edit bot."
PAGE = "http://127.0.0.1:4887"
PROVIDER = "https://api.provider.example/v1"
SETUP_CREDENTIAL = {
    "name": "first_model",
    "details": {"kind": "llm", "base_url": PROVIDER, "model": "provider-model"},
    "value": "sk-provider-key-1234",
    "bot_ids": [],
}
OTHER_PROVIDER = "https://api.other.example/v1"
OTHER_CREDENTIAL = {
    "name": "other_model",
    "details": {"kind": "llm", "base_url": OTHER_PROVIDER, "model": "other-model"},
    "value": "sk-other-key-5678",
    "bot_ids": [],
}
GITHUB_CREDENTIAL = {
    "name": "github",
    "details": {
        "kind": "custom",
        "destination": {"origin": "https://api.github.com", "auth": "bearer", "header_name": None},
    },
    "value": "ghp-github-key-1234",
    "bot_ids": [],
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
    bots: BotService
    secrets: SecretService


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
        yield App(client, runs, provider, bots, secrets)


async def _say(app: App, conversation_id: str) -> list[dict]:
    sent = await app.client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "hi"}
    )
    assert sent.status_code == 202, sent.text
    await settle(app.runs, conversation_id)
    return (await app.client.get(f"/api/conversations/{conversation_id}")).json()["events"]


async def _pick_model(app: App, bot_id: str, name: str | None) -> httpx.Response:
    bot = next(bot for bot in (await app.client.get("/api/bots")).json() if bot["id"] == bot_id)
    edit = {"name": bot["name"], "instructions": bot["instructions"], "model": name}
    return await app.client.put(f"/api/bots/{bot_id}", json=edit)


def _last_chunk(events: list[dict]) -> dict:
    return [event for event in events if event["type"] == "assistant/chunk"][-1]["chunk"]


async def test_setup_picks_assistant_a_model_and_a_bot_with_no_model_refuses(app: App) -> None:
    saved = await app.client.post("/api/credentials", json=SETUP_CREDENTIAL)
    assert saved.status_code == 201, saved.text
    picked = await _pick_model(app, ASSISTANT_ID, "first_model")
    assert picked.status_code == 200, picked.text

    await _say(app, ASSISTANT_ID)
    assert len(app.provider.requests) == 1

    events = await _say(app, BUILDER_ID)
    assert len(app.provider.requests) == 1
    assert _last_chunk(events) == {"kind": "failed", "reason": PICK_A_MODEL, "code": None}
    assert events[-1]["type"] == "turn/end"

    removed = await app.client.delete("/api/credentials/first_model")
    assert removed.status_code == 204, removed.text
    events = await _say(app, ASSISTANT_ID)
    assert len(app.provider.requests) == 1
    assert _last_chunk(events)["reason"] == PICK_A_MODEL


async def test_a_model_picked_in_edit_bot_answers_the_next_turn(app: App) -> None:
    for credential in (SETUP_CREDENTIAL, OTHER_CREDENTIAL):
        assert (await app.client.post("/api/credentials", json=credential)).status_code == 201
    made = await app.client.post("/api/bots", json={**RESEARCHER, "model": "first_model"})
    researcher = made.json()["id"]

    picked = await _pick_model(app, researcher, "other_model")
    assert picked.status_code == 200, picked.text
    assert picked.json()["model_credential"] == "other_model"
    await _say(app, researcher)

    (asked,) = app.provider.requests
    assert asked.url.host == "api.other.example"
    assert asked.headers["authorization"] == "Bearer sk-other-key-5678"

    assert (await _pick_model(app, researcher, None)).status_code == 200
    events = await _say(app, researcher)
    assert len(app.provider.requests) == 1
    assert _last_chunk(events)["reason"] == PICK_A_MODEL


@pytest.mark.parametrize("name", ["github", "no_such_model"])
async def test_a_name_that_is_not_an_llm_credential_is_refused(app: App, name: str) -> None:
    assert (await app.client.post("/api/credentials", json=GITHUB_CREDENTIAL)).status_code == 201

    refused = await _pick_model(app, ASSISTANT_ID, name)

    assert refused.status_code == 422, refused.text
    assistant = (await app.client.get("/api/bots")).json()[0]
    assert assistant["model_credential"] is None


async def test_an_llm_credential_refuses_ticked_bots(app: App) -> None:
    ticked = {**SETUP_CREDENTIAL, "bot_ids": [ASSISTANT_ID]}
    assert (await app.client.post("/api/credentials", json=ticked)).status_code == 422
    assert (await app.client.post("/api/credentials", json=SETUP_CREDENTIAL)).status_code == 201

    change = {"details": SETUP_CREDENTIAL["details"], "value": None, "bot_ids": [ASSISTANT_ID]}
    refused = await app.client.patch("/api/credentials/first_model", json=change)

    assert refused.status_code == 422, refused.text
    assistant = (await app.client.get("/api/bots")).json()[0]
    assert assistant["model_credential"] is None


async def _save_credentials(app: App, *credentials: dict) -> None:
    for credential in credentials:
        saved = await app.client.post("/api/credentials", json=credential)
        assert saved.status_code == 201, saved.text


async def _bot_create(app: App, model: str):
    arguments = json.dumps({**RESEARCHER, "model": model})
    return await bot_create_tool(app.bots, app.secrets).invoke(arguments, context=context_for())


@pytest.mark.parametrize(
    "body",
    [RESEARCHER, {**RESEARCHER, "model": "github"}, {**RESEARCHER, "model": "no_such_model"}],
)
async def test_a_bot_is_not_made_without_a_saved_llm_credential(app: App, body: dict) -> None:
    await _save_credentials(app, SETUP_CREDENTIAL, GITHUB_CREDENTIAL)

    refused = await app.client.post("/api/bots", json=body)

    assert refused.status_code == 422, refused.text
    assert len((await app.client.get("/api/bots")).json()) == 2


async def test_bot_create_with_an_unknown_model_names_the_saved_ones(app: App) -> None:
    await _save_credentials(app, SETUP_CREDENTIAL, OTHER_CREDENTIAL, GITHUB_CREDENTIAL)

    outcome = await _bot_create(app, "nvidia_model")

    assert isinstance(outcome, Failure)
    (text,) = outcome.content
    assert text.text.startswith("error:")
    assert "first_model" in text.text
    assert "other_model" in text.text
    assert "github" not in text.text
    assert len(await app.bots.active_bots()) == 2


async def test_a_bot_made_by_bot_create_answers_on_its_model(app: App) -> None:
    await _save_credentials(app, SETUP_CREDENTIAL, OTHER_CREDENTIAL)

    outcome = await _bot_create(app, "other_model")

    assert isinstance(outcome, Ok)
    made = (await app.bots.active_bots())[2]
    assert made.model_credential == "other_model"
    await _say(app, made.id)
    (asked,) = app.provider.requests
    assert asked.url.host == "api.other.example"
