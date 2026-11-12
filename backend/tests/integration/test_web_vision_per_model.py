"""Each LLM credential says whether it can see images, and a bot on one that cannot gets none."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID
from harness.config.settings import Settings
from harness.llm.adapters.openai import client as adapter_module
from harness.mcp import McpService
from harness.runs.service import RunService
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.native.files import VIEW_IMAGE
from harness.web.runtime import build_runtime
from tests.integration.test_web_no_model import PAGE, FakeProvider
from tests.integration.web_helpers import settle
from tests.mcp_stub import DOT_PNG
from tests.unit.helpers import client_tools, durable_service, no_approvals, no_skills
from tests.webapp import bots_in, files_in, images_in, secrets_in, web_app

DOT = base64.b64decode(DOT_PNG)
SEEING = "seeing_model"
TEXT_ONLY = "text_model"


def credential(name: str, base_url: str, *, vision: bool) -> dict:
    details = {"kind": "llm", "base_url": base_url, "model": name, "vision": vision}
    return {"name": name, "details": details, "value": f"sk-{name}-key", "bot_ids": []}


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
    runtime = build_runtime(
        Settings(),
        service,
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=bots,
        subagent_logs=SessionService(JsonlSessionRepository(tmp_path / "subagents")),
        secrets=secrets,
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )
    runs = RunService(service, runtime, bots, app_events=AppEventService())
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


async def _send_image(app: App, chat_id: str) -> None:
    uploaded = await app.client.post(
        f"/api/conversations/{chat_id}/files", files={"file": ("page.png", DOT, "image/png")}
    )
    assert uploaded.status_code == 201, uploaded.text
    sent = await app.client.post(
        f"/api/conversations/{chat_id}/messages",
        json={"prompt": "look", "files": [uploaded.json()["path"]]},
    )
    assert sent.status_code == 202, sent.text
    await settle(app.runs, chat_id)


def _request_to(provider: FakeProvider, host: str) -> dict:
    (request,) = [request for request in provider.requests if request.url.host == host]
    return json.loads(request.content)


def _image_blocks(body: dict) -> list[dict]:
    return [
        block
        for message in body["messages"]
        if isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "image_url"
    ]


def _tool_names(body: dict) -> list[str]:
    return [tool["function"]["name"] for tool in body.get("tools", [])]


async def test_only_a_bot_on_a_seeing_model_is_sent_images_and_view_image(app: App) -> None:
    for saved in (
        credential(SEEING, "https://api.seeing.example/v1", vision=True),
        credential(TEXT_ONLY, "https://api.text.example/v1", vision=False),
    ):
        assert (await app.client.post("/api/credentials", json=saved)).status_code == 201
    researcher = {"name": "Researcher", "instructions": "Find sources.", "model": TEXT_ONLY}
    reader = (await app.client.post("/api/bots", json=researcher)).json()["id"]
    edit = {"name": "Assistant", "instructions": "Help.", "model": SEEING}
    assert (await app.client.put(f"/api/bots/{ASSISTANT_ID}", json=edit)).status_code == 200

    await _send_image(app, ASSISTANT_ID)
    await _send_image(app, reader)

    seeing = _request_to(app.provider, "api.seeing.example")
    assert len(_image_blocks(seeing)) == 1
    assert VIEW_IMAGE in _tool_names(seeing)
    text_only = _request_to(app.provider, "api.text.example")
    assert _image_blocks(text_only) == []
    assert VIEW_IMAGE not in _tool_names(text_only)


@pytest.mark.parametrize(
    ("base_url", "status"),
    [
        ("http://api.example.com/v1", 422),
        ("http://127.0.0.1:1234/v1", 201),
        ("http://localhost:1234/v1", 201),
        ("https://api.example.com/v1", 201),
    ],
)
async def test_plain_http_is_saved_only_for_this_computer(
    app: App, base_url: str, status: int
) -> None:
    saved = await app.client.post(
        "/api/credentials", json=credential(SEEING, base_url, vision=True)
    )

    assert saved.status_code == status, saved.text
