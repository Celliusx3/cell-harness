"""What the dialog's saves refuse, each with the headers that let the page read why."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from harness.bots import BotService
from harness.secrets import DiskSecretRepository, SecretService
from harness.web.errors import exception_handlers
from harness.web.routes.credentials import build_router
from tests.unit.helpers import durable_service

KEY = "0123456789abcdef0123456789abcdef"
PAGE = "http://localhost:4887"
GITHUB = {
    "name": "github",
    "details": {
        "kind": "custom",
        "destination": {"origin": "https://api.github.com", "auth": "bearer"},
    },
    "value": "ghp-new-key-1234",
    "bot_ids": [],
}
MODEL_DETAILS = {"kind": "llm", "base_url": "https://api.example.com/v1", "model": "big"}


@pytest.fixture
def http(tmp_path: Path) -> httpx.AsyncClient:
    secrets = SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)
    bots = BotService(
        tmp_path / "bots.json", durable_service(tmp_path / "sessions"), assistant_instructions="Hi."
    )
    app = FastAPI(exception_handlers=exception_handlers())
    app.include_router(build_router(secrets, bots))
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
    return httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1:4886", headers={"origin": PAGE}
    )


async def _names(http: httpx.AsyncClient) -> list[str]:
    return [c["name"] for c in (await http.get("/api/credentials")).json()["credentials"]]


async def test_a_credential_cannot_change_its_type(http: httpx.AsyncClient) -> None:
    async with http:
        await http.post("/api/credentials", json=GITHUB)
        response = await http.patch(
            "/api/credentials/github",
            json={"details": MODEL_DETAILS, "value": None, "bot_ids": []},
        )
        listed = (await http.get("/api/credentials")).json()["credentials"]

    assert response.status_code == 409
    assert response.headers["access-control-allow-origin"] == PAGE
    assert listed[0]["details"]["kind"] == "custom"


async def test_changing_or_removing_a_credential_nobody_saved_is_a_404(
    http: httpx.AsyncClient,
) -> None:
    async with http:
        changed = await http.patch(
            "/api/credentials/nope", json={"details": MODEL_DETAILS, "value": None, "bot_ids": []}
        )
        removed = await http.delete("/api/credentials/nope")

    assert (changed.status_code, removed.status_code) == (404, 404)
    assert "'nope'" in removed.json()["detail"]


async def test_ticking_a_bot_nobody_made_saves_nothing(http: httpx.AsyncClient) -> None:
    async with http:
        response = await http.post("/api/credentials", json={**GITHUB, "bot_ids": ["nope"]})
        names = await _names(http)

    assert response.status_code == 404
    assert names == []


async def test_a_refused_key_is_answered_so_the_page_can_read_why(
    http: httpx.AsyncClient,
) -> None:
    async with http:
        response = await http.post("/api/credentials", json={**GITHUB, "value": "short"})

    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == PAGE
    assert "printable ASCII" in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize("path", ["/api/credentials", "/api/credentials/github"])
async def test_the_preflight_grants_a_page_on_this_mac_and_no_other(
    http: httpx.AsyncClient, path: str
) -> None:
    async with http:
        granted = await http.options(path)
        withheld = await http.options(path, headers={"origin": "https://evil.example"})

    assert "PATCH" in granted.headers["access-control-allow-methods"]
    assert "access-control-allow-origin" not in withheld.headers
