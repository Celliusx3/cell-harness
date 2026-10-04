"""Every event keeps its number in the stream."""

from __future__ import annotations

import httpx

from tests.integration.web_helpers import build, settle
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills
from tests.webapp import web_app


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
