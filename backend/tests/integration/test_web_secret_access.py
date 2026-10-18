"""One keyring for every key, and each bot uses only the keys the person allowed it."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from harness.bots import ASSISTANT_ID, BotDraft, GroupDraft
from harness.secrets import SecretService
from harness.tools import ApprovalGate
from harness.tools.client import ClientToolService
from harness.tools.native.secrets import ASK_FOR_SECRET, FETCH_WITH_SECRET, fetch_with_secret_tool
from harness.web.runtime import CLIENT_TOOLS
from tests.integration.web_helpers import events_from, settle
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, durable_service, no_skills, run_service
from tests.webapp import bots_in, web_app

KEY = "tok-9Zx=7Lm/q+Abc"
ASK = json.dumps(
    {"name": "github", "origin": "https://api.github.com", "auth": "bearer", "label": "GitHub"}
)
FETCH = json.dumps(
    {"name": "github", "url": "https://api.github.com/notifications", "method": "GET"}
)
APPROVE_ONCE = {"kind": "approved", "scope": "once"}


async def _post(client: httpx.AsyncClient, runs, chat_id: str, path: str, body) -> None:
    response = await client.post(f"/api/conversations/{chat_id}{path}", json=body)
    assert response.status_code in (202, 204), response.text
    await settle(runs, chat_id)


async def _result(client: httpx.AsyncClient, chat_id: str, call_id: str) -> dict:
    stream = (await client.get(f"/api/conversations/{chat_id}/events?after=0")).text
    return next(
        e
        for e in events_from(stream)
        if e["type"] == "tool/result" and e["message"]["tool_call_id"] == call_id
    )


async def _bots_allowed(client: httpx.AsyncClient) -> dict[str, list[str]]:
    return {bot["id"]: bot["secret_names"] for bot in (await client.get("/api/bots")).json()}


async def test_a_bot_uses_a_saved_key_only_once_the_person_allows_it(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []
    gate = ApprovalGate(frozenset({FETCH_WITH_SECRET}), frozenset, tmp_path / "approvals.json")
    tools = ClientToolService(CLIENT_TOOLS, gate)
    secrets = SecretService(tmp_path / "secrets.json", encryption_key="test-encryption-key")
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    model = SteppedClient(
        calls_tool(ASK_FOR_SECRET, ASK, id="call_ask"),
        calls_tool(FETCH_WITH_SECRET, FETCH, id="call_fetch"),
        completed("You have notifications."),
        calls_tool(FETCH_WITH_SECRET, FETCH, id="call_refused"),
        completed("I may not use it."),
        calls_tool(FETCH_WITH_SECRET, FETCH, id="call_allowed"),
        completed("Now I can."),
    )

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="{}")

    fetch = fetch_with_secret_tool(secrets, bots, httpx.MockTransport(answer))
    runs = run_service(service, model, fetch, *tools.definitions(), gate=gate, bots=bots)
    app = web_app(
        tmp_path,
        service,
        runs,
        skills=no_skills(),
        client_tools=tools,
        gate=gate,
        bots=bots,
        secrets=secrets,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://h.test") as client:
        await _post(client, runs, ASSISTANT_ID, "/messages", {"prompt": "check my GitHub"})
        await _post(client, runs, ASSISTANT_ID, "/calls/call_ask/secret", {"value": KEY})
        await _post(client, runs, ASSISTANT_ID, "/calls/call_fetch/output", APPROVE_ONCE)
        assert len(seen) == 1

        listed = (await client.get("/api/secrets")).json()
        assert listed == [
            {
                "name": "github",
                "origin": "https://api.github.com",
                "auth": "bearer",
                "header_name": None,
                "bots": [{"id": ASSISTANT_ID, "name": "Assistant"}],
            }
        ]
        assert KEY not in json.dumps(listed)

        notion = await bots.create(BotDraft(name="Notion", instructions="You read Notion."))
        chat = bots.chat_of(notion.id)
        await _post(client, runs, chat, "/messages", {"prompt": "check my GitHub"})
        await _post(client, runs, chat, "/calls/call_refused/output", APPROVE_ONCE)
        refused = await _result(client, chat, "call_refused")
        assert refused["error"] == "NOT_ALLOWED"
        assert "may not use 'github'" in refused["message"]["content"][0]["text"]
        assert len(seen) == 1

        allowed = await client.put(f"/api/bots/{notion.id}/secrets", json={"names": ["github"]})
        assert allowed.status_code == 200, allowed.text
        assert (await _bots_allowed(client))[notion.id] == ["github"]
        await _post(client, runs, chat, "/messages", {"prompt": "try again"})
        await _post(client, runs, chat, "/calls/call_allowed/output", APPROVE_ONCE)
        assert (await _result(client, chat, "call_allowed"))["error"] is None
        assert len(seen) == 2

        removed = await client.delete("/api/secrets/github")
        assert removed.status_code == 204, removed.text
        assert (await client.get("/api/secrets")).json() == []
        assert all("github" not in names for names in (await _bots_allowed(client)).values())


async def test_a_bot_cannot_be_allowed_a_key_that_is_not_saved(tmp_path: Path) -> None:
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    runs = run_service(service, SteppedClient(completed("hi")), bots=bots)
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=bots)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://h.test") as client:
        response = await client.put(f"/api/bots/{ASSISTANT_ID}/secrets", json={"names": ["nope"]})

    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


async def _launch(tmp_path: Path):
    """A group of Researcher then Writer, where Writer asks for a key on its turn."""
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    tools = client_tools()
    model = SteppedClient(
        completed("Sources."), calls_tool(ASK_FOR_SECRET, ASK, id="call_ask"), completed("Saved.")
    )
    runs = run_service(service, model, *tools.definitions(), bots=bots)
    app = web_app(tmp_path, service, runs, skills=no_skills(), client_tools=tools, bots=bots)
    researcher = await bots.create(BotDraft(name="Researcher", instructions="Cite."))
    writer = await bots.create(BotDraft(name="Writer", instructions="Post."))
    group = await bots.create_group(
        GroupDraft(name="Launch", member_ids=(researcher.id, writer.id))
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")
    return client, runs, group.id, researcher.id, writer.id


async def test_in_a_group_the_saved_key_goes_to_the_bot_that_asked_for_it(tmp_path: Path) -> None:
    client, runs, group, researcher, writer = await _launch(tmp_path)
    async with client:
        await _post(client, runs, group, "/messages", {"prompt": "post it on GitHub"})
        await _post(client, runs, group, "/calls/call_ask/secret", {"value": KEY})
        allowed = await _bots_allowed(client)

    assert allowed[writer] == ["github"]
    assert allowed[researcher] == []


async def test_a_key_for_a_bot_archived_since_it_asked_is_refused(tmp_path: Path) -> None:
    client, runs, group, _, writer = await _launch(tmp_path)
    async with client:
        await _post(client, runs, group, "/messages", {"prompt": "post it on GitHub"})
        assert (await client.post(f"/api/bots/{writer}/archive")).status_code == 204
        saved = await client.post(
            f"/api/conversations/{group}/calls/call_ask/secret", json={"value": KEY}
        )
        keys = (await client.get("/api/secrets")).json()

    assert saved.status_code == 409
    assert keys == []
