"""A key typed into a card reaches the API it was saved for and nothing the model or a log reads."""

from __future__ import annotations

import base64
import json
import stat
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID, BotDraft
from harness.llm import StreamEvent
from harness.runs.service import RunService
from harness.secrets import SECRET_VALUE_RULE, Destination, SecretRefused, SecretService
from harness.tools import ApprovalService
from harness.tools.client import ClientToolService
from harness.tools.native.secrets import ASK_FOR_SECRET, FETCH_WITH_SECRET, fetch_with_secret_tool
from harness.web.runtime import CLIENT_TOOLS
from tests.integration.web_helpers import events_from, settle
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import bots_in, secrets_in, web_app

KEY = 'tok-"q/+9Zx=7Lm'
ECHOES = (KEY, json.dumps(KEY)[1:-1], quote(KEY, safe=""), base64.b64encode(KEY.encode()).decode())
ASK = json.dumps(
    {
        "name": "github",
        "origin": "https://api.github.com",
        "auth": "bearer",
        "label": "GitHub token",
    }
)
FETCH = json.dumps(
    {"name": "github", "url": "https://api.github.com/notifications", "method": "GET"}
)
APPROVE_ONCE = {"kind": "approved", "scope": "once"}


def _echoing(seen: list[httpx.Request]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=" | ".join(ECHOES))

    return httpx.MockTransport(handle)


async def _post(client: httpx.AsyncClient, runs, conversation_id: str, path: str, body) -> None:
    response = await client.post(f"/api/conversations/{conversation_id}{path}", json=body)
    assert response.status_code in (202, 204), response.text
    await settle(runs, conversation_id)


def _results(events: list[dict]) -> dict[str, dict]:
    return {e["message"]["tool_call_id"]: e for e in events if e["type"] == "tool/result"}


def _leaks(text: str) -> list[str]:
    return [form for form in (KEY, json.dumps(KEY)[1:-1]) if form in text]


async def test_a_saved_key_reaches_its_site_and_never_the_model_or_the_log(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    approvals = ApprovalService(
        frozenset({FETCH_WITH_SECRET}), frozenset, tmp_path / "approvals.json"
    )
    tools = ClientToolService(CLIENT_TOOLS, approvals)
    secrets = secrets_in(tmp_path)
    model = SteppedClient(
        calls_tool(ASK_FOR_SECRET, ASK, id="call_ask"),
        calls_tool(FETCH_WITH_SECRET, FETCH, id="call_fetch"),
        completed("You have notifications."),
        calls_tool(FETCH_WITH_SECRET, FETCH, id="call_other"),
        completed("I have no GitHub key."),
    )
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    fetch = fetch_with_secret_tool(secrets, bots, _echoing(seen))
    runs = run_service(service, model, fetch, *tools.tools(), approvals=approvals, bots=bots)
    app = web_app(
        tmp_path,
        service,
        runs,
        skills=no_skills(),
        client_tools=tools,
        approvals=approvals,
        bots=bots,
        secrets=secrets,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://h.test") as client:
        await _post(client, runs, ASSISTANT_ID, "/messages", {"prompt": "check my GitHub"})
        await _post(client, runs, ASSISTANT_ID, "/calls/call_ask/secret", {"value": KEY})
        await _post(client, runs, ASSISTANT_ID, "/calls/call_fetch/output", APPROVE_ONCE)

        stored = (tmp_path / "secrets.json").read_text(encoding="utf-8")
        assert _leaks(stored) == []
        assert stat.S_IMODE((tmp_path / "secrets.json").stat().st_mode) == 0o600

        assert [request.headers["authorization"] for request in seen] == [f"Bearer {KEY}"]
        assert str(seen[0].url) == "https://api.github.com/notifications"

        stream = (await client.get(f"/api/conversations/{ASSISTANT_ID}/events?after=0")).text
        results = _results(events_from(stream))
        assert json.loads(results["call_ask"]["message"]["content"][0]["text"]) == {
            "name": "github"
        }
        fetched = json.loads(results["call_fetch"]["message"]["content"][0]["text"])
        assert fetched["status"] == 200
        assert fetched["body"] == " | ".join(["[secret]"] * len(ECHOES))
        assert _leaks(stream) == []

        other = await bots.create(BotDraft(name="Notion", instructions="You read Notion."))
        await _post(client, runs, other.id, "/messages", {"prompt": "check my GitHub"})
        await _post(client, runs, other.id, "/calls/call_other/output", APPROVE_ONCE)
        other_stream = (await client.get(f"/api/conversations/{other.id}/events?after=0")).text
        refused = _results(events_from(other_stream))["call_other"]
        assert refused["error"] == "NOT_ALLOWED"
        assert "may not use" in refused["message"]["content"][0]["text"]
        assert len(seen) == 1

    logged = "".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "sessions").rglob("*") if p.is_file()
    )
    assert _leaks(logged) == []


def _asking_app(
    tmp_path: Path, first: list[StreamEvent]
) -> tuple[httpx.AsyncClient, RunService, SecretService]:
    approvals = ApprovalService(
        frozenset({FETCH_WITH_SECRET}), frozenset, tmp_path / "approvals.json"
    )
    tools = ClientToolService(CLIENT_TOOLS, approvals)
    secrets = secrets_in(tmp_path)
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    fetch = fetch_with_secret_tool(secrets, bots, _echoing([]))
    model = SteppedClient(first, completed("Saved."))
    runs = run_service(service, model, fetch, *tools.tools(), approvals=approvals, bots=bots)
    app = web_app(
        tmp_path,
        service,
        runs,
        skills=no_skills(),
        client_tools=tools,
        approvals=approvals,
        bots=bots,
        secrets=secrets,
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")
    return client, runs, secrets


async def _save(client: httpx.AsyncClient, call_id: str, body: dict) -> httpx.Response:
    return await client.post(f"/api/conversations/{ASSISTANT_ID}/calls/{call_id}/secret", json=body)


async def _waiting(client: httpx.AsyncClient) -> set[str]:
    stream = (await client.get(f"/api/conversations/{ASSISTANT_ID}/events?after=0")).text
    events = events_from(stream)
    called = {e["call"]["id"] for e in events if e["type"] == "tool/call"}
    return called - set(_results(events))


async def test_a_key_that_breaks_the_rule_is_a_422_naming_the_rule_not_the_key(tmp_path) -> None:
    client, runs, secrets = _asking_app(tmp_path, calls_tool(ASK_FOR_SECRET, ASK, id="call_ask"))
    async with client:
        await _post(client, runs, ASSISTANT_ID, "/messages", {"prompt": "check my GitHub"})

        refused = await _save(client, "call_ask", {"value": f" {KEY}"})

        assert refused.status_code == 422
        assert SECRET_VALUE_RULE in refused.text
        assert _leaks(refused.text) == []
        assert secrets.secret_named("github") is None
        assert await _waiting(client) == {"call_ask"}


async def test_a_call_not_waiting_for_a_key_is_a_404_and_nothing_is_saved(tmp_path) -> None:
    client, runs, _ = _asking_app(tmp_path, calls_tool(FETCH_WITH_SECRET, FETCH, id="call_fetch"))
    async with client:
        await _post(client, runs, ASSISTANT_ID, "/messages", {"prompt": "check my GitHub"})

        unknown = await _save(client, "call_unknown", {"value": KEY})
        approval = await _save(client, "call_fetch", {"value": KEY})

        assert (unknown.status_code, approval.status_code) == (404, 404)
        assert await _waiting(client) == {"call_fetch"}
    assert not (tmp_path / "secrets.json").exists()


async def test_a_body_naming_its_own_site_is_refused_and_the_site_is_the_calls(tmp_path) -> None:
    client, runs, secrets = _asking_app(tmp_path, calls_tool(ASK_FOR_SECRET, ASK, id="call_ask"))
    async with client:
        await _post(client, runs, ASSISTANT_ID, "/messages", {"prompt": "check my GitHub"})

        refused = await _save(client, "call_ask", {"value": KEY, "origin": "https://evil.example"})
        assert refused.status_code == 422
        assert secrets.secret_named("github") is None

        await _post(client, runs, ASSISTANT_ID, "/calls/call_ask/secret", {"value": KEY})

    saved = secrets.secret_named("github")
    assert saved is not None
    assert saved.destination.origin == "https://api.github.com"


async def test_a_save_the_store_refuses_is_a_409_with_its_reason_and_still_waits(tmp_path) -> None:
    client, runs, secrets = _asking_app(tmp_path, calls_tool(ASK_FOR_SECRET, ASK, id="call_ask"))
    elsewhere = Destination(origin="https://other.example", auth="bearer")
    secrets.save("github", elsewhere, SecretStr("an-older-key"))
    asked = Destination(origin="https://api.github.com", auth="bearer")
    with pytest.raises(SecretRefused) as expected:
        secrets.save("github", asked, SecretStr(KEY))
    async with client:
        await _post(client, runs, ASSISTANT_ID, "/messages", {"prompt": "check my GitHub"})

        refused = await _save(client, "call_ask", {"value": KEY})

        assert refused.status_code == 409
        assert str(expected.value) in refused.text
        assert await _waiting(client) == {"call_ask"}
