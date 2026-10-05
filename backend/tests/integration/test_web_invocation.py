"""`/name` over HTTP."""

from __future__ import annotations

import httpx

from harness.bots import ASSISTANT_ID
from tests.integration.web_helpers import assistant_chat, build, settle
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import skills_at
from tests.unit.test_skill_tool import write_skill
from tests.webapp import web_app


async def test_a_skill_name_is_expanded(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    service, runs = build(tmp_path, ScriptedClient(completed("Village Park")))
    app = web_app(tmp_path, service, runs, skills=skills_at(root))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        conversation_id = await assistant_chat(c, "/find-place https://x")
        await settle(runs, conversation_id)

        detail = (await c.get(f"/api/conversations/{conversation_id}")).json()

    (content,) = [e["message"]["content"] for e in detail["events"] if e["type"] == "user/message"]
    assert content.startswith('/find-place https://x\n\n<skill name="find-place">')


async def test_an_unknown_skill_name_is_a_422_and_starts_nothing(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    service, runs = build(tmp_path, ScriptedClient(completed("never")))
    app = web_app(tmp_path, service, runs, skills=skills_at(root))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        refused = await c.post(
            f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": "/summarise this"}
        )
        assert refused.status_code == 422
        assert refused.json()["detail"] == (
            "No skill named 'summarise'. Skills: /find-place. Commands: /new, /stop, /compact."
        )
        assert list((tmp_path / "sessions").glob("*.jsonl")) == []

        conversation_id = await assistant_chat(c, "hello")
        await settle(runs, conversation_id)
        sent = await c.post(
            f"/api/conversations/{conversation_id}/messages", json={"prompt": "/nope"}
        )
        assert sent.status_code == 422
        assert "No skill named 'nope'" in sent.json()["detail"]
