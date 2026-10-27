"""The bot page lists the keyring startup is given, and refuses a bot nobody made."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from harness.bots import ASSISTANT_ID
from harness.secrets import Destination
from harness.web import server
from tests.unit.fakes import SteppedClient, completed
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import bots_in, secrets_in, startup_settings, web_app

GITHUB = Destination(origin="https://api.github.com", auth="bearer")


def _client(tmp_path: Path) -> httpx.AsyncClient:
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    secrets = secrets_in(tmp_path)
    secrets.save("github", GITHUB, SecretStr("tok-9Zx=7Lm"))
    runs = run_service(service, SteppedClient(completed("hi")), bots=bots)
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=secrets)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")


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


async def test_startup_lists_the_keys_in_the_configured_keyring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secrets_in(tmp_path).save("github", GITHUB, SecretStr("tok-9Zx=7Lm"))
    monkeypatch.setattr(server, "load", lambda: startup_settings(tmp_path))
    monkeypatch.setattr(server, "configure_logging", lambda: None)
    transport = httpx.ASGITransport(app=server.create_web_app())

    async with httpx.AsyncClient(transport=transport, base_url="http://h.test") as client:
        listed = (await client.get("/api/secrets")).json()

    assert [key["name"] for key in listed] == ["github"]
