"""`POST /api/skills`: a zipped skill folder installed whole, or refused with a reason."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest

from harness.skills import archive, skill_tool
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import skills_at
from tests.webapp import web_app

NOTES = "---\nname: notes\ndescription: Take notes.\n---\n# Notes\n\nSee references/style.md.\n"
STYLE = "# Style\n\nShort sentences.\n"


def write_skill(root: Path, name: str, text: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(text)


def zipped(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as inside:
        for path, text in files.items():
            inside.writestr(path, text)
    return buffer.getvalue()


def linked(path: str, target: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as inside:
        inside.writestr("notes/SKILL.md", NOTES)
        info = zipfile.ZipInfo(path)
        info.external_attr = 0o120777 << 16
        inside.writestr(info, target)
    return buffer.getvalue()


def upload(data: bytes) -> dict[str, tuple[str, bytes, str]]:
    return {"file": ("skill.zip", data, "application/zip")}


@pytest.fixture
def api(tmp_path):
    """A project root that outranks the editable home root, as in config.json."""
    project = tmp_path / "project"
    home = tmp_path / "home"
    write_skill(project, "pdf", "---\ndescription: PDFs.\n---\nbody\n")
    home.mkdir(parents=True)
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, skills=skills_at(project, home))
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return client, project, home


async def test_a_zipped_folder_installs_with_its_bundled_files(api) -> None:
    client, _project, home = api
    data = zipped({"notes/SKILL.md": NOTES, "notes/references/style.md": STYLE})

    async with client:
        response = await client.post("/api/skills", files=upload(data))
        listing = await client.get("/api/skills")

    assert response.status_code == 201
    assert response.json()["name"] == "notes"
    assert response.json()["editable"] is True
    assert (home / "notes" / "SKILL.md").read_text() == NOTES
    assert (home / "notes" / "references" / "style.md").read_text() == STYLE
    assert [skill["name"] for skill in listing.json()["skills"]] == ["pdf", "notes"]
    assert listing.json()["skills"][1]["editable"] is True


async def test_the_name_comes_from_the_folder_not_the_frontmatter(api) -> None:
    client, _project, home = api
    data = zipped({"jotter/SKILL.md": "---\ndescription: Jot.\n---\nbody\n"})

    async with client:
        response = await client.post("/api/skills", files=upload(data))

    assert response.status_code == 201
    assert response.json()["name"] == "jotter"
    assert (home / "jotter" / "SKILL.md").is_file()


async def test_a_frontmatter_name_that_differs_from_the_folder_is_refused(api) -> None:
    client, _project, home = api
    data = zipped({"jotter/SKILL.md": NOTES})

    async with client:
        response = await client.post("/api/skills", files=upload(data))

    assert response.status_code == 422
    assert "notes" in response.json()["detail"]
    assert not (home / "jotter").exists()


async def test_installing_again_replaces_the_whole_directory(api) -> None:
    client, _project, home = api
    first = zipped({"notes/SKILL.md": NOTES, "notes/references/style.md": STYLE})
    again = "---\nname: notes\ndescription: Take notes.\n---\n# Notes\n\nFewer files.\n"
    second = zipped({"notes/SKILL.md": again})

    async with client:
        await client.post("/api/skills", files=upload(first))
        response = await client.post("/api/skills", files=upload(second))

    assert response.status_code == 201
    assert (home / "notes" / "SKILL.md").read_text() == again
    assert not (home / "notes" / "references").exists()


async def test_a_name_the_project_root_owns_is_a_conflict(api) -> None:
    client, _project, home = api
    data = zipped({"pdf/SKILL.md": "---\nname: pdf\ndescription: Mine.\n---\nbody\n"})

    async with client:
        response = await client.post("/api/skills", files=upload(data))

    assert response.status_code == 409
    assert not (home / "pdf").exists()


@pytest.mark.parametrize(
    ("files", "reason"),
    [
        ({"SKILL.md": NOTES}, "top-level"),
        ({"notes/SKILL.md": NOTES, "other/SKILL.md": NOTES}, "top-level"),
        ({"notes/references/style.md": STYLE}, "SKILL.md"),
        ({"notes/../escape.md": STYLE, "notes/SKILL.md": NOTES}, "escape"),
        ({"/etc/passwd": STYLE, "notes/SKILL.md": NOTES}, "escape"),
        ({"Notes/SKILL.md": NOTES}, "skill name"),
        ({"notes/SKILL.md": "no frontmatter here\n"}, "frontmatter"),
    ],
)
async def test_a_zip_the_catalog_could_not_load_is_refused(api, files, reason) -> None:
    client, _project, home = api

    async with client:
        response = await client.post("/api/skills", files=upload(zipped(files)))

    assert response.status_code == 422
    assert reason in response.json()["detail"]
    assert list(home.iterdir()) == []


async def test_a_link_inside_the_archive_is_refused(api) -> None:
    client, _project, home = api

    async with client:
        data = linked("notes/key", "/etc/passwd")
        response = await client.post("/api/skills", files=upload(data))

    assert response.status_code == 422
    assert "link" in response.json()["detail"]
    assert list(home.iterdir()) == []


async def test_what_the_finder_adds_beside_the_folder_is_ignored(api) -> None:
    client, _project, home = api
    data = zipped(
        {
            "notes/SKILL.md": NOTES,
            "notes/.DS_Store": "junk",
            "__MACOSX/._notes": "junk",
            "notes/scripts/__pycache__/render.cpython-313.pyc": "junk",
        }
    )

    async with client:
        response = await client.post("/api/skills", files=upload(data))

    assert response.status_code == 201
    assert sorted(p.name for p in (home / "notes").iterdir()) == ["SKILL.md"]


async def test_something_that_is_not_a_zip_is_refused(api) -> None:
    client, _project, home = api

    async with client:
        response = await client.post("/api/skills", files=upload(b"not a zip at all"))

    assert response.status_code == 422
    assert "zip" in response.json()["detail"]
    assert list(home.iterdir()) == []


async def test_an_archive_over_the_unpacked_cap_is_refused(api, monkeypatch) -> None:
    client, _project, home = api
    monkeypatch.setattr(archive, "MAX_UNPACKED_BYTES", 32)

    async with client:
        response = await client.post("/api/skills", files=upload(zipped({"notes/SKILL.md": NOTES})))

    assert response.status_code == 422
    assert "large" in response.json()["detail"]
    assert list(home.iterdir()) == []


async def test_an_archive_with_too_many_files_is_refused(api, monkeypatch) -> None:
    client, _project, home = api
    monkeypatch.setattr(archive, "MAX_FILES", 1)
    data = zipped({"notes/SKILL.md": NOTES, "notes/references/style.md": STYLE})

    async with client:
        response = await client.post("/api/skills", files=upload(data))

    assert response.status_code == 422
    assert "files" in response.json()["detail"]
    assert list(home.iterdir()) == []


async def test_a_skill_arrives_whole_with_references_scripts_and_assets(api) -> None:
    client, _project, home = api
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as inside:
        inside.writestr("invoice/SKILL.md", NOTES.replace("notes", "invoice"))
        inside.writestr("invoice/references/format.md", STYLE)
        inside.writestr("invoice/references/templates/line-items.md", STYLE)
        inside.writestr("invoice/scripts/render.py", "print('rendered')\n")
        inside.writestr("invoice/assets/logo.png", b"\x89PNG\r\n\x1a\n\x00binary")

    async with client:
        response = await client.post("/api/skills", files=upload(buffer.getvalue()))

    assert response.status_code == 201
    inside_skill = home / "invoice"
    written = sorted(
        p.relative_to(inside_skill).as_posix() for p in inside_skill.rglob("*") if p.is_file()
    )
    assert written == [
        "SKILL.md",
        "assets/logo.png",
        "references/format.md",
        "references/templates/line-items.md",
        "scripts/render.py",
    ]
    assert (home / "invoice" / "assets" / "logo.png").read_bytes().startswith(b"\x89PNG")


async def test_an_uploaded_script_is_listed_and_readable_but_never_run(api) -> None:
    client, _project, home = api
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as inside:
        inside.writestr("invoice/SKILL.md", NOTES.replace("notes", "invoice"))
        inside.writestr("invoice/references/format.md", STYLE)
        inside.writestr("invoice/scripts/render.py", "print('rendered')\n")

    async with client:
        await client.post("/api/skills", files=upload(buffer.getvalue()))

    tool = skill_tool(skills_at(home))
    assert tool is not None
    loaded = (await tool.execute(tool.parse({"name": "invoice"}), None)).text
    assert "Bundled files, readable with `path`: references/format.md, scripts/render.py" in loaded

    script = tool.parse({"name": "invoice", "path": "scripts/render.py"})
    source = (await tool.execute(script, None)).text
    assert "print('rendered')" in source
    assert "Any other script cannot run" in tool.description
