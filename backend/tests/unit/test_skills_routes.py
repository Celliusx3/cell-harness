"""`/api/skills`: the catalog as a person sees it, and the one root they may write."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import skills_at
from tests.webapp import web_app

VALID = "---\nname: notes\ndescription: Take notes.\n---\n# Notes\n\nWrite them down.\n"


def write_skill(root: Path, name: str, text: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(text)


@pytest.fixture
def api(tmp_path):
    """A project root that outranks the editable home root, as in config.json."""
    project = tmp_path / "project"
    home = tmp_path / "home"
    write_skill(project, "pdf", "---\ndescription: PDFs.\nuser-invocable: false\n---\nbody\n")
    write_skill(project, "broken", "not a skill\n")
    write_skill(home, "mine", "---\ndescription: Mine.\n---\nbody\n")
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, skills=skills_at(project, home))
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return client, project, home


async def test_the_listing_carries_skills_problems_and_editability(api) -> None:
    client, project, home = api
    async with client:
        response = await client.get("/api/skills")

    assert response.status_code == 200
    body = response.json()
    assert body["skills"] == [
        {
            "name": "pdf",
            "description": "PDFs.",
            "dir": str(project / "pdf"),
            "root": str(project),
            "model_invocable": True,
            "user_invocable": False,
            "editable": False,
        },
        {
            "name": "mine",
            "description": "Mine.",
            "dir": str(home / "mine"),
            "root": str(home),
            "model_invocable": True,
            "user_invocable": True,
            "editable": True,
        },
    ]
    (problem,) = body["problems"]
    assert problem["path"] == str(project / "broken" / "SKILL.md")
    assert "---" in problem["problem"]


async def test_a_skill_added_after_startup_is_listed(api) -> None:
    client, project, _ = api
    async with client:
        write_skill(project, "new", "---\ndescription: New.\n---\n")
        response = await client.get("/api/skills")

    assert [s["name"] for s in response.json()["skills"]] == ["new", "pdf", "mine"]


async def test_reading_one_returns_its_file(api) -> None:
    client, _, _ = api
    async with client:
        mine = await client.get("/api/skills/mine")
        pdf = await client.get("/api/skills/pdf")
        none = await client.get("/api/skills/nope")

    assert mine.json() == {
        "name": "mine",
        "text": "---\ndescription: Mine.\n---\nbody\n",
        "editable": True,
        "files": [],
    }
    assert pdf.json()["editable"] is False
    assert none.status_code == 404


async def test_saving_writes_to_the_editable_root_and_it_is_listed(api) -> None:
    client, _, home = api
    async with client:
        saved = await client.put("/api/skills/notes", json={"text": VALID})
        listed = await client.get("/api/skills")

    assert saved.status_code == 204
    assert (home / "notes" / "SKILL.md").read_text() == VALID
    assert [s["name"] for s in listed.json()["skills"]] == ["pdf", "mine", "notes"]


async def test_saving_an_existing_editable_skill_overwrites_it(api) -> None:
    client, _, home = api
    async with client:
        saved = await client.put(
            "/api/skills/mine", json={"text": "---\ndescription: Mine, v2.\n---\nnew body\n"}
        )
        read = await client.get("/api/skills/mine")

    assert saved.status_code == 204
    assert read.json()["text"].endswith("new body\n")
    assert (home / "mine" / "SKILL.md").read_text().endswith("new body\n")


@pytest.mark.parametrize(
    ("name", "text", "reason"),
    [
        ("Bad Name", VALID, "name"),
        ("notes", "no frontmatter\n", "---"),
        ("notes", "---\nname: other\ndescription: d\n---\nbody\n", "'other'"),
        ("notes", "---\ndescription: \n---\nbody\n", "description"),
    ],
)
async def test_a_skill_the_catalog_would_not_load_is_refused(api, name, text, reason) -> None:
    client, _, home = api
    async with client:
        response = await client.put(f"/api/skills/{name}", json={"text": text})

    assert response.status_code == 422
    assert reason in response.json()["detail"]
    assert not (home / name).exists()


async def test_saving_a_name_the_project_root_owns_is_refused(api) -> None:
    client, project, home = api
    async with client:
        response = await client.put(
            "/api/skills/pdf", json={"text": "---\ndescription: mine now\n---\nbody\n"}
        )

    assert response.status_code == 409
    assert str(project / "pdf") in response.json()["detail"]
    assert not (home / "pdf").exists()


async def test_deleting_removes_the_directory(api) -> None:
    client, _, home = api
    (home / "mine" / "references").mkdir()
    (home / "mine" / "references" / "x.md").write_text("bundled")
    async with client:
        deleted = await client.delete("/api/skills/mine")
        listed = await client.get("/api/skills")

    assert deleted.status_code == 204
    assert not (home / "mine").exists()
    assert [s["name"] for s in listed.json()["skills"]] == ["pdf"]


async def test_deleting_outside_the_editable_root_is_refused(api) -> None:
    client, project, _ = api
    async with client:
        response = await client.delete("/api/skills/pdf")

    assert response.status_code == 409
    assert str(project) in response.json()["detail"]
    assert (project / "pdf" / "SKILL.md").exists()


async def test_deleting_an_unknown_skill_is_a_404(api) -> None:
    client, _, _ = api
    async with client:
        assert (await client.delete("/api/skills/nope")).status_code == 404
