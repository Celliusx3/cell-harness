"""Every event keeps its number: in the stream, and across a clear that wipes the chat."""

from __future__ import annotations

import httpx

from harness.tools.native.question import QUESTION
from tests.integration.web_helpers import build, settle
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, no_skills
from tests.webapp import web_app

ASKS = calls_tool(QUESTION, '{"question": "Which shop?", "options": ["A", "B"]}', id="call_q")


def _client(tmp_path, model, *tools) -> tuple[httpx.AsyncClient, object]:
    service, runs = build(tmp_path, model, *tools)
    app = web_app(tmp_path, service, runs, skills=no_skills())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), runs


def _numbers(body: str) -> list[int]:
    frames = [block for block in body.split("\n\n") if "event: session" in block]
    return [
        int(line.removeprefix("id: "))
        for frame in frames
        for line in frame.split("\n")
        if line.startswith("id: ")
    ]


async def _started(client: httpx.AsyncClient, runs, prompt: str) -> str:
    cid = (await client.post("/api/conversations", json={"prompt": prompt})).json()["id"]
    await settle(runs, cid)
    return cid


async def test_every_streamed_event_carries_its_number(tmp_path) -> None:
    client, runs = _client(tmp_path, ScriptedClient(completed("hi")))
    async with client:
        cid = await _started(client, runs, "hello")
        total = (await client.get(f"/api/conversations/{cid}")).json()["next_cursor"]
        body = (await client.get(f"/api/conversations/{cid}/events?after=2")).text

    assert _numbers(body) == list(range(2, total))


async def test_a_clear_removes_earlier_messages_from_disk(tmp_path) -> None:
    client, runs = _client(tmp_path, ScriptedClient(completed("noted")))
    async with client:
        cid = await _started(client, runs, "the secret word is PELICAN")
        assert (await client.post(f"/api/conversations/{cid}/clear")).status_code == 204

    stored = (tmp_path / "sessions" / f"{cid}.jsonl").read_text(encoding="utf-8")
    assert "PELICAN" not in stored


async def test_numbering_carries_on_after_a_clear(tmp_path) -> None:
    client, runs = _client(tmp_path, ScriptedClient(completed("noted")))
    async with client:
        cid = await _started(client, runs, "hello")
        before = (await client.get(f"/api/conversations/{cid}")).json()["next_cursor"]
        await client.post(f"/api/conversations/{cid}/clear")
        after = (await client.get(f"/api/conversations/{cid}")).json()
        from_an_old_tab = (await client.get(f"/api/conversations/{cid}/events?after=3")).text

    assert [event["type"] for event in after["events"]] == ["chat/cleared"]
    assert after["next_cursor"] == before + 1
    assert _numbers(from_an_old_tab) == [before]


async def test_a_tap_on_a_card_from_before_the_clear_is_refused(tmp_path) -> None:
    tools = client_tools()
    service, runs = build(tmp_path, SteppedClient(ASKS), *tools.definitions())
    app = web_app(tmp_path, service, runs, skills=no_skills(), client_tools=tools)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        cid = await _started(c, runs, "find a shop")
        await c.post(f"/api/conversations/{cid}/clear")
        tapped = await c.post(
            f"/api/conversations/{cid}/calls/call_q/output",
            json={"kind": "shared", "data": {"choice": "A"}},
        )

    assert tapped.status_code == 404
