"""`POST /api/conversations/{id}/compact` — the manual compaction over HTTP."""

from __future__ import annotations

import httpx

from harness.bots import ASSISTANT_ID
from harness.channels.protocol import InboundMessage
from tests.integration.web_helpers import assistant_chat, settle
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_store
from tests.webapp import idle, web_app, web_app_with_telegram


def app_over(tmp_path, *, summary: str = "SUMMARY", context=None):
    """A web app whose agent compacts through the same scripted client."""
    service = durable_service(tmp_path / "sessions")
    client = ScriptedClient(completed(summary))
    runs = run_store(service, client, context_tokens=context)
    app = web_app(tmp_path, service, runs, skills=no_skills())
    return service, runs, app


async def test_a_compact_summarizes_and_the_next_view_starts_with_the_summary(tmp_path) -> None:
    service, runs, app = app_over(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        cid = await assistant_chat(c, "hello there")
        await settle(runs, cid)

        accepted = await c.post(f"/api/conversations/{cid}/compact")
        assert accepted.status_code == 202
        await settle(runs, cid)

        detail = (await c.get(f"/api/conversations/{cid}")).json()

    types = [e["type"] for e in detail["events"]]
    assert "compaction/start" in types and "compaction/end" in types
    end = next(e for e in detail["events"] if e["type"] == "compaction/end")
    assert end["message"] is not None and "SUMMARY" in end["message"]["content"]


async def test_compacting_a_running_conversation_is_a_409(tmp_path) -> None:
    from tests.unit.fakes import HangingClient

    service = durable_service(tmp_path / "sessions")
    runs = run_store(service, HangingClient("thinking"))
    app = web_app(tmp_path, service, runs, skills=no_skills())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        cid = await assistant_chat(c, "hello there")
        conflict = await c.post(f"/api/conversations/{cid}/compact")
        assert conflict.status_code == 409
    await runs.stop(cid)


async def test_nothing_to_compact_is_a_409_with_the_reason(tmp_path) -> None:
    service, runs, app = app_over(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        cid = await assistant_chat(c, "hello there")
        await settle(runs, cid)
        await c.post(f"/api/conversations/{cid}/compact")
        await settle(runs, cid)

        again = await c.post(f"/api/conversations/{cid}/compact")
        assert again.status_code == 409
        assert again.json()["detail"] == "nothing to compact"


async def test_compacting_an_unknown_conversation_is_a_404(tmp_path) -> None:
    service, runs, app = app_over(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        missing = await c.post("/api/conversations/nope/compact")
        assert missing.status_code == 404


async def test_a_failed_summary_leaves_the_conversation_unchanged(tmp_path) -> None:
    from harness.llm.stream import Failed

    service = durable_service(tmp_path / "sessions")

    class TwoScripts(ScriptedClient):
        def __init__(self):
            super().__init__(completed("reply"))

        async def stream_completion(self, messages, model, *, tools=None):
            if tools is None:
                yield Failed(reason="boom")
                return
            for e in completed("reply"):
                yield e

    client = TwoScripts()
    runs = run_store(service, client, context_tokens=None)
    app = web_app(tmp_path, service, runs, skills=no_skills())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        cid = await assistant_chat(c, "hello there")
        await settle(runs, cid)
        await c.post(f"/api/conversations/{cid}/compact")
        await settle(runs, cid)
        detail = (await c.get(f"/api/conversations/{cid}")).json()

    ends = [e for e in detail["events"] if e["type"] == "compaction/end"]
    assert ends and ends[-1]["message"] is None and ends[-1]["error"]


async def test_a_browser_compaction_sends_nothing_to_telegram(tmp_path) -> None:
    service = durable_service(tmp_path / "sessions")
    client = ScriptedClient(completed("SUMMARY"))
    runs = run_store(service, client, context_tokens=None)
    app, gateway, bot = web_app_with_telegram(tmp_path, service, runs, skills=no_skills())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await gateway.receive(InboundMessage(channel="telegram", chat_id="909", text="hello"))
        await idle(runs, gateway)

        accepted = await c.post(f"/api/conversations/{ASSISTANT_ID}/compact")
        assert accepted.status_code == 202
        await idle(runs, gateway)
        detail = (await c.get(f"/api/conversations/{ASSISTANT_ID}")).json()

    assert any(e["type"] == "compaction/end" for e in detail["events"])
    assert bot.sent == [("909", "SUMMARY")]
