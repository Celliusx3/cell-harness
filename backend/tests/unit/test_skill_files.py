"""`/api/skills/{name}`: the files a skill brought with it, and reading one."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import skills_at
from tests.webapp import web_app

VALID = "---\nname: invoice\ndescription: Invoices.\n---\nbody\n"


def write_skill(root: Path, name: str, text: str) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(text)
    return directory


@pytest.fixture
def api(tmp_path):
    home = tmp_path / "home"
    directory = write_skill(home, "invoice", VALID)
    (directory / "references").mkdir()
    (directory / "references" / "rules.md").write_text("Rules.")
    (directory / "references" / "templates").mkdir()
    (directory / "references" / "templates" / "line.md").write_text("Line.")
    (directory / "scripts").mkdir()
    (directory / "scripts" / "digit.py").write_text("print('hi')\n")
    (directory / "assets").mkdir()
    (directory / "assets" / "logo.png").write_bytes(b"\x89PNG\xff\xfe\x00")
    (directory / "big.txt").write_text("x" * (64 * 1024 + 1))
    write_skill(home, "bare", "---\nname: bare\ndescription: Nothing bundled.\n---\nbody\n")
    (tmp_path / "secret.txt").write_text("no")

    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, skills=skills_at(home))
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return client, home


async def test_a_skill_carries_the_files_it_brought_with_it(api) -> None:
    client, _home = api

    async with client:
        response = await client.get("/api/skills/invoice")

    assert response.status_code == 200
    body = response.json()
    assert body["files"] == [
        "assets/logo.png",
        "big.txt",
        "references/rules.md",
        "references/templates/line.md",
        "scripts/digit.py",
    ]
    assert body["text"] == VALID


async def test_a_skill_with_nothing_bundled_carries_an_empty_list(api) -> None:
    client, _home = api

    async with client:
        response = await client.get("/api/skills/bare")

    assert response.json()["files"] == []


async def test_a_bundled_file_is_read_by_path(api) -> None:
    client, _home = api

    async with client:
        response = await client.get("/api/skills/invoice/files/references/templates/line.md")

    assert response.status_code == 200
    assert response.json() == {"path": "references/templates/line.md", "text": "Line."}


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("%2e%2e/secret.txt", "not inside"),
        ("%2e%2e/%2e%2e/secret.txt", "not inside"),
        ("scripts/%2e%2e/%2e%2e/bare/SKILL.md", "not inside"),
        ("nope.md", "no file"),
        ("assets/logo.png", "not a text"),
        ("big.txt", "KiB"),
    ],
)
async def test_a_file_the_skill_may_not_hand_over_is_refused(api, path, reason) -> None:
    client, _home = api

    async with client:
        response = await client.get(f"/api/skills/invoice/files/{path}")

    assert response.status_code == 422
    assert reason in response.json()["detail"]


async def test_a_literal_dot_segment_never_reaches_the_server(api) -> None:
    """Any RFC 3986 client collapses `..` itself, so the escape must be encoded to be tested."""
    client, _home = api

    async with client:
        response = await client.get("/api/skills/invoice/files/../secret.txt")

    assert response.status_code == 404


async def test_an_unknown_skill_has_no_files(api) -> None:
    client, _home = api

    async with client:
        response = await client.get("/api/skills/nothing/files/references/rules.md")

    assert response.status_code == 404
