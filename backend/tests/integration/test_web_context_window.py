"""Each LLM credential's endpoint says its own window, and each bot compacts at its model's."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID, BotService
from harness.config.sections import CompactionSettings, LLMSettings
from harness.llm.adapters import OpenAIClient
from harness.llm.adapters.openai import client as adapter_module
from harness.runs.service.run_service import RunService
from harness.runtime.service import Runtime
from harness.web.model_choice import CredentialModels, ModelEndpoint
from harness.web.runtime import compaction_window_tokens
from tests.bot_models import put_on_model
from tests.integration.test_web_no_model import PAGE, no_image
from tests.integration.web_helpers import settle
from tests.unit.group_helpers import group_service
from tests.unit.helpers import durable_service, no_images, no_skills
from tests.webapp import bots_in, secrets_in, web_app

SMALL_HOST = "api.small.example"
LARGE_HOST = "api.large.example"
WINDOWS = {SMALL_HOST: 8000, LARGE_HOST: 32000}
USED_TOKENS = 7000
SUMMARY_ASK = "compaction engine"


def _credential(name: str, host: str) -> dict:
    details = {"kind": "llm", "base_url": f"https://{host}/v1", "model": "m", "vision": False}
    return {"name": name, "details": details, "value": f"sk-{name}-1234", "bot_ids": []}


def _sse(*payloads: dict) -> bytes:
    return "".join(f"data: {json.dumps(p)}\n\n" for p in payloads).encode() + b"data: [DONE]\n\n"


@dataclass
class WindowedProvider:
    """Endpoints that list one model with each host's window and report `USED_TOKENS` per reply."""

    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET":
            window = WINDOWS[request.url.host]
            return httpx.Response(200, json={"data": [{"id": "m", "context_length": window}]})
        usage = {"choices": [], "usage": {"prompt_tokens": USED_TOKENS, "completion_tokens": 0}}
        delta = {"choices": [{"delta": {"content": "hello"}}]}
        return httpx.Response(200, content=_sse(delta, usage))

    def asked(self, host: str, method: str = "POST") -> list[httpx.Request]:
        return [r for r in self.requests if r.url.host == host and r.method == method]

    def asked_with(self, text: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == "POST" and text in r.content.decode()]


@dataclass(frozen=True)
class App:
    client: httpx.AsyncClient
    runs: RunService
    provider: WindowedProvider
    bots: BotService


def _runtime(models: CredentialModels, checkpoint) -> Runtime:
    return Runtime(models=models, images=no_images(), tools=None, checkpoint=checkpoint)


def _patch_endpoints(monkeypatch: pytest.MonkeyPatch, provider: WindowedProvider) -> None:
    real_async, real_sync = httpx.AsyncClient, httpx.Client
    monkeypatch.setattr(
        adapter_module.httpx,
        "AsyncClient",
        lambda **kwargs: real_async(transport=httpx.MockTransport(provider), **kwargs),
    )
    monkeypatch.setattr(
        adapter_module.httpx,
        "Client",
        lambda **kwargs: real_sync(transport=httpx.MockTransport(provider), **kwargs),
    )


@pytest.fixture
async def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    secrets = secrets_in(tmp_path)
    base = LLMSettings()
    endpoint = ModelEndpoint(
        client_for=lambda s: OpenAIClient(s, read_image=no_image),
        blocking_window_for=lambda s: compaction_window_tokens(
            CompactionSettings(context_tokens=None), s
        ),
    )
    runs = RunService(
        service,
        _runtime(CredentialModels(secrets, bots, base, endpoint), service.flush),
        bots,
        group_service(bots, service),
        app_events=AppEventService(),
    )
    asgi = web_app(tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=secrets)
    transport = httpx.ASGITransport(app=asgi, client=("127.0.0.1", 50000))
    client = httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1:4886", headers={"origin": PAGE}
    )
    provider = WindowedProvider()
    _patch_endpoints(monkeypatch, provider)
    async with client:
        for name, host in (("small_model", SMALL_HOST), ("large_model", LARGE_HOST)):
            saved = await client.post("/api/credentials", json=_credential(name, host))
            assert saved.status_code == 201, saved.text
        put_on_model(bots, ASSISTANT_ID, "small_model")
        yield App(client, runs, provider, bots)


async def _researcher_on_large(app: App) -> str:
    made = await app.client.post(
        "/api/bots", json={"name": "Researcher", "instructions": "Find.", "model": "large_model"}
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


async def _say(app: App, conversation_id: str, prompt: str = "hi") -> list[dict]:
    sent = await app.client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": prompt}
    )
    assert sent.status_code == 202, sent.text
    await settle(app.runs, conversation_id)
    return (await app.client.get(f"/api/conversations/{conversation_id}")).json()["events"]


def _compactions(events: list[dict]) -> list[dict]:
    return [event for event in events if event["type"] == "compaction/start"]


async def test_each_bot_compacts_at_its_own_credentials_window(app: App) -> None:
    researcher = await _researcher_on_large(app)

    for _ in range(2):
        small = await _say(app, ASSISTANT_ID)
        large = await _say(app, researcher)

    assert [event["tokens"] for event in _compactions(small)] == [USED_TOKENS]
    assert _compactions(large) == []
    (summary,) = app.provider.asked_with(SUMMARY_ASK)
    assert summary.url.host == SMALL_HOST


async def test_the_window_is_asked_once_over_two_turns(app: App) -> None:
    researcher = await _researcher_on_large(app)

    for _ in range(2):
        await _say(app, ASSISTANT_ID)
        await _say(app, researcher)

    for host in (SMALL_HOST, LARGE_HOST):
        (listed,) = app.provider.asked(host, method="GET")
        assert listed.url.path == "/v1/models"


async def test_a_new_version_of_the_credential_is_asked_again(app: App) -> None:
    await _say(app, ASSISTANT_ID)
    change = {
        "details": _credential("small_model", SMALL_HOST)["details"],
        "value": "sk-new-key-5678",
        "bot_ids": [],
    }
    changed = await app.client.patch("/api/credentials/small_model", json=change)
    assert changed.status_code == 200, changed.text

    await _say(app, ASSISTANT_ID)

    assert len(app.provider.asked(SMALL_HOST, method="GET")) == 2


async def test_a_manual_compaction_asks_the_chats_bots_credential(app: App) -> None:
    researcher = await _researcher_on_large(app)
    await _say(app, researcher)

    accepted = await app.client.post(f"/api/conversations/{researcher}/compact")
    assert accepted.status_code == 202, accepted.text
    await settle(app.runs, researcher)

    (summary,) = app.provider.asked_with(SUMMARY_ASK)
    assert summary.url.host == LARGE_HOST
    assert app.provider.asked(SMALL_HOST) == []
