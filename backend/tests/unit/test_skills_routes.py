"""`GET /api/skills`: the catalog as a person sees it."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from harness.skills import SkillCatalog
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.webapp import web_app


def write_skill(root: Path, name: str, text: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(text)


@pytest.fixture
def api(tmp_path):
    root = tmp_path / "skills"
    write_skill(root, "pdf", "---\ndescription: PDFs.\nuser-invocable: false\n---\nbody\n")
    write_skill(root, "broken", "not a skill\n")
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, skills=SkillCatalog([root]))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), root


async def test_the_listing_carries_skills_and_problems(api) -> None:
    client, root = api
    async with client:
        response = await client.get("/api/skills")

    assert response.status_code == 200
    body = response.json()
    assert body["skills"] == [
        {
            "name": "pdf",
            "description": "PDFs.",
            "dir": str(root / "pdf"),
            "root": str(root),
            "model_invocable": True,
            "user_invocable": False,
        }
    ]
    (problem,) = body["problems"]
    assert problem["path"] == str(root / "broken" / "SKILL.md")
    assert "---" in problem["problem"]


async def test_a_skill_added_after_startup_is_listed(api) -> None:
    client, root = api
    async with client:
        write_skill(root, "new", "---\ndescription: New.\n---\n")
        response = await client.get("/api/skills")

    assert [s["name"] for s in response.json()["skills"]] == ["new", "pdf"]
