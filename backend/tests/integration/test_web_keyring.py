"""The Keys page's routes refuse a key nobody saved and a bot nobody made."""

from __future__ import annotations

from pathlib import Path

import httpx
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID
from harness.secrets import Destination
from tests.unit.fakes import SteppedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import bots_in, secrets_in, web_app

GITHUB = Destination(origin="https://api.github.com", auth="bearer")


def _client(tmp_path: Path) -> httpx.AsyncClient:
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    secrets = secrets_in(tmp_path)
    secrets.save("github", GITHUB, SecretStr("tok-9Zx=7Lm"))
    runs = run_service(service, SteppedClient(completed("hi")), bots=bots)
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=secrets)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")


async def test_removing_a_key_nobody_saved_is_a_404_naming_it(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.delete("/api/secrets/notion")
        listed = (await client.get("/api/secrets")).json()

    assert response.status_code == 404
    assert "'notion'" in response.json()["detail"]
    assert [key["name"] for key in listed] == ["github"]


async def test_allowing_a_key_to_a_bot_nobody_made_is_a_404(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.put("/api/bots/nope/secrets", json={"names": ["github"]})

    assert response.status_code == 404
    assert "'nope'" in response.json()["detail"]


async def test_a_body_with_more_than_names_is_refused(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        response = await client.put(
            f"/api/bots/{ASSISTANT_ID}/secrets", json={"names": ["github"], "value": "tok"}
        )

    assert response.status_code == 422
