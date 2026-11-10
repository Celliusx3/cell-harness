"""The app starts from a config that names no model, and Assistant asks for one until it has it."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from harness.app_events import AppEvents
from harness.bots import ASSISTANT_ID
from harness.config import settings as settings_module
from harness.llm.adapters.openai import client as adapter_module
from harness.runs.service import RunService
from harness.web import server
from tests.integration.web_helpers import settle
from tests.webapp import TEST_ENCRYPTION_KEY

PICK_A_MODEL = "Pick a model for this bot in Edit bot."
PAGE = "http://127.0.0.1:4887"
FIRST_MODEL = {
    "name": "first_model",
    "details": {
        "kind": "llm",
        "base_url": "https://api.provider.example/v1",
        "model": "provider-model",
        "vision": False,
    },
    "value": "sk-provider-key-1234",
    "bot_ids": [],
}


@dataclass
class FakeProvider:
    """An OpenAI-compatible endpoint that answers every request with one short reply."""

    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        delta = json.dumps({"choices": [{"delta": {"content": "hello"}}]})
        return httpx.Response(200, content=f"data: {delta}\n\ndata: [DONE]\n\n".encode())


@dataclass(frozen=True)
class Started:
    client: httpx.AsyncClient
    runs: RunService
    provider: FakeProvider


def _config_with_no_model(tmp_path: Path) -> Path:
    committed = tmp_path / "config.json"
    config = {
        "llm": {"temperature": 1.0, "timeout_seconds": 600},
        "sessions": {"root": str(tmp_path / "sessions")},
        "files": {"root": str(tmp_path / "files")},
        "bots": {"path": str(tmp_path / "bots.json")},
        "secrets": {"path": str(tmp_path / "secrets.json"), "encryption_key": TEST_ENCRYPTION_KEY},
        "approval": {"grants_path": str(tmp_path / "approvals.json")},
        "skills": {"roots": [str(tmp_path / "skills")], "editable": str(tmp_path / "skills")},
        "compaction": {"context_tokens": 1000},
        "mcp": {"path": str(tmp_path / "mcp.json")},
    }
    committed.write_text(json.dumps(config), encoding="utf-8")
    return committed


def _started_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[FastAPI, list[RunService]]:
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", _config_with_no_model(tmp_path))
    monkeypatch.setattr(server, "configure_logging", lambda: None)
    built: list[RunService] = []

    def runs_seen(*args, events: AppEvents) -> RunService:
        runs = RunService(*args, events=events)
        built.append(runs)
        return runs

    monkeypatch.setattr(server, "RunService", runs_seen)
    return server.create_web_app(), built


@pytest.fixture
async def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app, built = _started_app(tmp_path, monkeypatch)
    provider = FakeProvider()
    real = httpx.AsyncClient
    monkeypatch.setattr(
        adapter_module.httpx,
        "AsyncClient",
        lambda **kwargs: real(transport=httpx.MockTransport(provider), **kwargs),
    )
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    client = real(transport=transport, base_url="http://127.0.0.1:4886", headers={"origin": PAGE})
    async with client:
        [runs] = built
        yield Started(client, runs, provider)
        await runs.aclose()


async def _say_to_assistant(started: Started) -> dict:
    sent = await started.client.post(
        f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": "hi"}
    )
    assert sent.status_code == 202, sent.text
    await settle(started.runs, ASSISTANT_ID)
    events = (await started.client.get(f"/api/conversations/{ASSISTANT_ID}")).json()["events"]
    return [event for event in events if event["type"] == "assistant/chunk"][-1]["chunk"]


async def test_the_credentials_list_offers_no_model_to_start_from(started: Started) -> None:
    listed = await started.client.get("/api/credentials")

    assert listed.status_code == 200, listed.text
    assert set(listed.json()) == {"credentials", "direct_url"}
    assert listed.json()["credentials"] == []


async def test_assistant_asks_for_a_model_until_a_credential_is_set(started: Started) -> None:
    assert (await _say_to_assistant(started))["reason"] == PICK_A_MODEL
    assert started.provider.requests == []

    saved = await started.client.post("/api/credentials", json=FIRST_MODEL)
    assert saved.status_code == 201, saved.text
    assistant = (await started.client.get("/api/bots")).json()[0]
    edit = {
        "name": assistant["name"],
        "instructions": assistant["instructions"],
        "model": "first_model",
    }
    picked = await started.client.put(f"/api/bots/{ASSISTANT_ID}", json=edit)
    assert picked.status_code == 200, picked.text

    assert (await _say_to_assistant(started))["full_text"] == "hello"
    (asked,) = started.provider.requests
    assert asked.url.host == "api.provider.example"
