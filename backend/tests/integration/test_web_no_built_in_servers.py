"""The app starts from the committed config with no MCP server; one added is offered."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID
from harness.config import settings as settings_module
from harness.llm.adapters.openai import client as adapter_module
from harness.runs.service.run_service import RunService
from harness.tools.native.code_mode.prompts import LIST_FUNCTIONS
from harness.tools.native.tickets import TICKET_ROUTE
from harness.web import server
from tests.integration.web_helpers import settle
from tests.webapp import TEST_ENCRYPTION_KEY

BACKEND = Path(__file__).resolve().parents[2]
STUB = BACKEND / "tests" / "mcp_stub.py"
PAGE = "http://127.0.0.1:4887"
TIMEOUT = 30.0
MODEL = {
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
LIST_CALL = {"index": 0, "id": "call-1", "function": {"name": LIST_FUNCTIONS, "arguments": "{}"}}
ACCEPT = json.dumps(
    {"items": [{"kind": "accept", "title": "Look", "task": "List what you can do."}]}
)
ROUTE_CALL = {"index": 0, "id": "route-1", "function": {"name": TICKET_ROUTE, "arguments": ACCEPT}}
STUB_SERVER = {
    "id": "stub",
    "command": sys.executable,
    "args": ["-u", str(STUB)],
    "env": {},
    "needs": [],
    "keys": {},
}


@dataclass
class FakeProvider:
    """An endpoint whose bot routes each message to a worker, who lists the functions on offer."""

    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        fresh = not any(message["role"] == "tool" for message in body["messages"])
        offered = {tool["function"]["name"] for tool in body.get("tools", [])}
        last = body["messages"][-1]
        typed = last["role"] == "user" and "<ticket id=" not in json.dumps(last)
        if fresh and LIST_FUNCTIONS in offered:
            delta: dict[str, object] = {"tool_calls": [LIST_CALL]}
        elif typed and TICKET_ROUTE in offered:
            delta = {"tool_calls": [ROUTE_CALL]}
        else:
            delta = {"content": "hello"}
        sent = json.dumps({"choices": [{"delta": delta}]})
        return httpx.Response(200, content=f"data: {sent}\n\ndata: [DONE]\n\n".encode())

    def listed_after(self, start: int) -> str | None:
        """The first request since `start` that carries what `list_functions` said."""
        for request in self.requests[start:]:
            body = json.loads(request.content)
            if any(message["role"] == "tool" for message in body["messages"]):
                names = {tool["function"]["name"] for tool in body.get("tools", [])}
                if LIST_FUNCTIONS in names:
                    return request.content.decode()
        return None


def _committed_config_in(tmp_path: Path) -> Path:
    """The committed `config.json`, its data paths moved under `tmp_path`, nothing else."""
    committed = json.loads((BACKEND / "config.json").read_text())
    moved = {
        "sessions": {"root": str(tmp_path / "sessions")},
        "files": {**committed["files"], "root": str(tmp_path / "files")},
        "bots": {"path": str(tmp_path / "bots.json")},
        "schedules": {"path": str(tmp_path / "schedules.json")},
        "tickets": {"path": str(tmp_path / "tickets.json")},
        "secrets": {"path": str(tmp_path / "secrets.json"), "encryption_key": TEST_ENCRYPTION_KEY},
        "approval": {**committed["approval"], "grants_path": str(tmp_path / "approvals.json")},
        "skills": {"roots": [str(tmp_path / "skills")], "editable": str(tmp_path / "skills")},
        "mcp": {**committed.get("mcp", {}), "path": str(tmp_path / "mcp.json")},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps({**committed, **moved}), encoding="utf-8")
    return path


@pytest.fixture
async def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings_module, "_CONFIG_JSON", _committed_config_in(tmp_path))
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", tmp_path / "config.local.json")
    monkeypatch.setattr(server, "configure_logging", lambda: None)
    built: list[RunService] = []

    def runs_seen(*args, app_events: AppEventService) -> RunService:
        built.append(RunService(*args, app_events=app_events))
        return built[-1]

    monkeypatch.setattr(server, "RunService", runs_seen)
    provider = FakeProvider()
    real = httpx.AsyncClient
    monkeypatch.setattr(
        adapter_module.httpx,
        "AsyncClient",
        lambda **kwargs: real(transport=httpx.MockTransport(provider), **kwargs),
    )
    app = server.create_web_app()
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    client = real(transport=transport, base_url="http://127.0.0.1:4886", headers={"origin": PAGE})
    async with client:
        listed = (await client.get("/api/mcp/servers")).json()["servers"]
        assert listed == [], "the committed config declares an MCP server"
        async with app.router.lifespan_context(app):
            [runs] = built
            yield client, runs, provider


async def _assistant_on_a_model(client: httpx.AsyncClient) -> None:
    saved = await client.post("/api/credentials", json=MODEL)
    assert saved.status_code == 201, saved.text
    assistant = (await client.get("/api/bots")).json()[0]
    edit = {**{key: assistant[key] for key in ("name", "instructions")}, "model": "first_model"}
    picked = await client.put(f"/api/bots/{ASSISTANT_ID}", json=edit)
    assert picked.status_code == 200, picked.text


async def _turn(client: httpx.AsyncClient, runs: RunService, provider: FakeProvider) -> str:
    """One message to Assistant, routed to a worker: the request that holds what it listed."""
    start = len(provider.requests)
    sent = await client.post(f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": "hi"})
    assert sent.status_code == 202, sent.text
    await settle(runs, ASSISTANT_ID)
    for _ in range(int(TIMEOUT * 10)):
        listed = provider.listed_after(start)
        if listed is not None:
            return listed
        await asyncio.sleep(0.1)
    raise AssertionError("no worker listed the functions")


async def _connected(client: httpx.AsyncClient, server_id: str) -> dict:
    for _ in range(int(TIMEOUT * 10)):
        listed = (await client.get("/api/mcp/servers")).json()["servers"]
        entry = next(entry for entry in listed if entry["id"] == server_id)
        if entry["status"] != "connecting":
            return entry
        await asyncio.sleep(0.1)
    return entry


async def test_the_app_starts_with_no_mcp_server(started) -> None:
    client, runs, provider = started
    await _assistant_on_a_model(client)

    assert (await client.get("/api/mcp/servers")).json() == {"servers": []}
    assert (await client.get("/api/mcp")).json() == {"servers": []}
    offered = json.loads(await _turn(client, runs, provider))["tools"]
    assert not [tool for tool in offered if "__" in tool["function"]["name"]]


async def test_a_server_added_on_the_screen_is_listed_in_the_next_turn(started) -> None:
    client, runs, provider = started
    await _assistant_on_a_model(client)
    assert "stub__echo" not in await _turn(client, runs, provider)

    added = await client.post("/api/mcp/servers", json=STUB_SERVER)
    assert added.status_code == 201, added.text
    entry = await _connected(client, "stub")

    assert (entry["status"], entry["error"]) == ("connected", "")
    assert (await client.get("/api/mcp")).json() == {"servers": ["stub"]}
    assert "stub__echo" in await _turn(client, runs, provider)
