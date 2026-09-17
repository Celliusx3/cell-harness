"""`/name` over HTTP: the expansion in the log, the typed line as the title,
and a `422` for a name nobody may invoke."""

from __future__ import annotations

import httpx

from tests.integration.web_helpers import build, settle
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import skills_at
from tests.unit.test_skill_tool import write_skill
from tests.webapp import web_app


async def test_a_skill_name_is_expanded_and_the_title_stays_what_was_typed(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    service, runs = build(tmp_path, ScriptedClient(completed("Village Park")))
    app = web_app(tmp_path, service, runs, skills=skills_at(root))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        created = await c.post("/api/conversations", json={"prompt": "/find-place https://x"})
        conversation_id = created.json()["id"]
        await settle(runs, conversation_id)

        detail = (await c.get(f"/api/conversations/{conversation_id}")).json()
        listed = (await c.get("/api/conversations")).json()

    (content,) = [e["message"]["content"] for e in detail["events"] if e["type"] == "user/message"]
    assert content.startswith('/find-place https://x\n\n<skill name="find-place">')
    assert [row["title"] for row in listed] == ["/find-place https://x"]


async def test_an_unknown_skill_name_is_a_422_and_starts_nothing(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    service, runs = build(tmp_path, ScriptedClient(completed("never")))
    app = web_app(tmp_path, service, runs, skills=skills_at(root))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        created = await c.post("/api/conversations", json={"prompt": "/summarise this"})
        assert created.status_code == 422
        assert created.json()["detail"] == (
            "No skill named 'summarise'. Skills: /find-place. Commands: /new, /stop, /compact."
        )
        assert (await c.get("/api/conversations")).json() == []

        ok = await c.post("/api/conversations", json={"prompt": "hello"})
        conversation_id = ok.json()["id"]
        await settle(runs, conversation_id)
        sent = await c.post(
            f"/api/conversations/{conversation_id}/messages", json={"prompt": "/nope"}
        )
        assert sent.status_code == 422
        assert "No skill named 'nope'" in sent.json()["detail"]
