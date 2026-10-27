"""Adding, editing and removing a credential: tied to bots, saved only from this Mac."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from harness.bots import BotDraft, BotService
from harness.secrets import DiskSecretRepository, SecretService
from harness.web.routes.credentials import build_router
from tests.unit.helpers import durable_service
from tests.webapp import no_platforms

KEY = "0123456789abcdef0123456789abcdef"
PAGE = "http://127.0.0.1:4887"
THIS_MAC = ("127.0.0.1", 50000)
GITHUB_DETAILS = {
    "kind": "custom",
    "destination": {"origin": "https://api.github.com", "auth": "bearer"},
}
MODEL_DETAILS = {"kind": "llm", "base_url": "https://api.example.com/v1", "model": "big"}


@pytest.fixture
def secrets(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


@pytest.fixture
def bots(tmp_path: Path) -> BotService:
    return BotService(
        tmp_path / "bots.json",
        durable_service(tmp_path / "sessions"),
        assistant_instructions="Be kind.",
    )


def _client(secrets: SecretService, bots: BotService, peer=THIS_MAC) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(build_router(secrets, bots, no_platforms(secrets)))
    transport = httpx.ASGITransport(app=app, client=peer)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4886")


async def _send(
    secrets, bots, method: str, url: str, body=None, *, origin=PAGE, peer=THIS_MAC, **headers
):
    sent = {"origin": origin} if origin else {}
    async with _client(secrets, bots, peer) as http:
        return await http.request(method, url, json=body, headers={**sent, **headers})


async def _listed(secrets, bots) -> dict:
    async with _client(secrets, bots) as http:
        return {c["name"]: c for c in (await http.get("/api/credentials")).json()["credentials"]}


async def test_a_custom_key_is_added_for_the_bots_ticked(secrets, bots) -> None:
    chef = await bots.create(BotDraft(name="Chef", instructions="Cook."))

    response = await _send(
        secrets,
        bots,
        "POST",
        "/api/credentials",
        {
            "name": "github",
            "details": GITHUB_DETAILS,
            "value": "ghp-new-key-1234",
            "bot_ids": [chef.id],
        },
    )

    assert response.status_code == 201
    assert bots.active_bot(chef.id).secret_names == ("github",)
    assert (await _listed(secrets, bots))["github"]["bots"] == [{"id": chef.id, "name": "Chef"}]


async def test_an_llm_credential_serves_the_bots_ticked(secrets, bots) -> None:
    trader = await bots.create(BotDraft(name="Trader", instructions="Trade."))

    await _send(
        secrets,
        bots,
        "POST",
        "/api/credentials",
        {
            "name": "trader_model",
            "details": MODEL_DETAILS,
            "value": "sk-model-key-5678",
            "bot_ids": [trader.id],
        },
    )

    assert bots.active_bot(trader.id).model_credential == "trader_model"
    assert (await _listed(secrets, bots))["trader_model"]["bots"] == [
        {"id": trader.id, "name": "Trader"}
    ]


async def test_ticking_a_bot_in_another_llm_credential_moves_it(secrets, bots) -> None:
    trader = await bots.create(BotDraft(name="Trader", instructions="Trade."))
    for name in ("first_model", "second_model"):
        await _send(
            secrets,
            bots,
            "POST",
            "/api/credentials",
            {
                "name": name,
                "details": MODEL_DETAILS,
                "value": "sk-model-key-5678",
                "bot_ids": [trader.id],
            },
        )

    listed = await _listed(secrets, bots)

    assert bots.active_bot(trader.id).model_credential == "second_model"
    assert listed["first_model"]["bots"] == []
    assert listed["second_model"]["bots"] == [{"id": trader.id, "name": "Trader"}]


async def test_an_edit_with_no_key_keeps_the_saved_key(secrets, bots) -> None:
    await _send(
        secrets,
        bots,
        "POST",
        "/api/credentials",
        {
            "name": "trader_model",
            "details": MODEL_DETAILS,
            "value": "sk-model-key-5678",
            "bot_ids": [],
        },
    )

    response = await _send(
        secrets,
        bots,
        "PATCH",
        "/api/credentials/trader_model",
        {
            "details": {**MODEL_DETAILS, "model": "bigger"},
            "value": None,
            "bot_ids": [],
        },
    )

    listed = (await _listed(secrets, bots))["trader_model"]
    assert response.status_code == 200
    assert listed["details"]["model"] == "bigger"
    assert listed["last_four"] == "5678"


async def test_removing_a_credential_unties_it_from_its_bots(secrets, bots) -> None:
    trader = await bots.create(BotDraft(name="Trader", instructions="Trade."))
    await _send(
        secrets,
        bots,
        "POST",
        "/api/credentials",
        {
            "name": "trader_model",
            "details": MODEL_DETAILS,
            "value": "sk-model-key-5678",
            "bot_ids": [trader.id],
        },
    )
    await _send(
        secrets,
        bots,
        "POST",
        "/api/credentials",
        {
            "name": "github",
            "details": GITHUB_DETAILS,
            "value": "ghp-new-key-1234",
            "bot_ids": [trader.id],
        },
    )

    for name in ("trader_model", "github"):
        response = await _send(secrets, bots, "DELETE", f"/api/credentials/{name}")
        assert response.status_code == 204

    assert bots.active_bot(trader.id).model_credential is None
    assert bots.active_bot(trader.id).secret_names == ()
    assert await _listed(secrets, bots) == {}


async def test_a_name_already_taken_is_refused(secrets, bots) -> None:
    body = {"name": "github", "details": GITHUB_DETAILS, "value": "ghp-new-key-1234", "bot_ids": []}
    await _send(secrets, bots, "POST", "/api/credentials", body)

    response = await _send(
        secrets, bots, "POST", "/api/credentials", {**body, "details": MODEL_DETAILS}
    )

    assert response.status_code == 409


async def test_a_key_that_breaks_the_rule_is_refused_without_echoing_it(secrets, bots) -> None:
    response = await _send(
        secrets,
        bots,
        "POST",
        "/api/credentials",
        {
            "name": "github",
            "details": GITHUB_DETAILS,
            "value": "short",
            "bot_ids": [],
        },
    )

    assert response.status_code == 422
    assert "short" not in response.text


@pytest.mark.parametrize("header", ["x-forwarded-for", "x-forwarded-host", "forwarded"])
async def test_a_save_that_came_through_a_proxy_is_refused(secrets, bots, header) -> None:
    body = {"name": "github", "details": GITHUB_DETAILS, "value": "ghp-new-key-1234", "bot_ids": []}

    response = await _send(secrets, bots, "POST", "/api/credentials", body, **{header: "x"})

    assert response.status_code == 403
    assert await _listed(secrets, bots) == {}


@pytest.mark.parametrize("origin", ["https://evil.example", "http://192.168.1.5:4887", None])
async def test_a_save_from_a_page_not_on_this_mac_is_refused(secrets, bots, origin) -> None:
    body = {"name": "github", "details": GITHUB_DETAILS, "value": "ghp-new-key-1234", "bot_ids": []}

    response = await _send(secrets, bots, "POST", "/api/credentials", body, origin=origin)

    assert response.status_code == 403


async def test_a_save_from_another_device_is_refused(secrets, bots) -> None:
    body = {"name": "github", "details": GITHUB_DETAILS, "value": "ghp-new-key-1234", "bot_ids": []}

    response = await _send(
        secrets, bots, "POST", "/api/credentials", body, peer=("192.168.1.5", 50000)
    )

    assert response.status_code == 403


async def test_the_list_tells_the_page_the_harness_own_address(secrets, bots) -> None:
    async with _client(secrets, bots) as http:
        response = await http.get("/api/credentials", headers={"origin": PAGE})

    assert response.json()["direct_url"] == "http://127.0.0.1:4886"
    assert response.headers["access-control-allow-origin"] == PAGE
