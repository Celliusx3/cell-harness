"""`GET /api/credentials`: every credential by kind, with its bots, never a key in full."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from harness.bots import BotDraft, BotService
from harness.secrets import Destination, DiskSecretRepository, SecretService
from harness.secrets.models.details import ModelDetails, TelegramDetails
from harness.secrets.models.sealed import SealedSecret
from harness.secrets.sealing import sealed
from harness.web.routes.credentials import build_router
from tests.unit.helpers import durable_service

KEY = "0123456789abcdef0123456789abcdef"
GITHUB = Destination(origin="https://api.github.com", auth="bearer")
GITHUB_KEY = "ghp-secret-key-1234"
MODEL_KEY = "sk-model-secret-5678"
TELEGRAM_TOKEN = "123456:AAtelegram-token-9012"


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


def _add_sealed(tmp_path: Path, name: str, details, value: str) -> None:
    repository = DiskSecretRepository(tmp_path / "secrets.json")
    record_id = f"{len(repository.sealed_secrets()) + 10:02x}"
    entry = SealedSecret(
        id=record_id,
        name=name,
        details=details,
        ciphertext=sealed(value, encryption_key=KEY, record_id=record_id),
    )
    repository.replace_all((*repository.sealed_secrets(), entry))


async def _listed(secrets: SecretService, bots: BotService) -> httpx.Response:
    app = FastAPI()
    app.include_router(build_router(secrets, bots))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
        return await http.get("/api/credentials")


async def test_every_kind_is_listed_by_name_with_its_last_four_characters(
    tmp_path: Path, secrets: SecretService, bots: BotService
) -> None:
    secrets.save("github", GITHUB, SecretStr(GITHUB_KEY))
    model = ModelDetails(base_url="https://api.example.com/v1", model="big")
    _add_sealed(tmp_path, "trader_model", model, MODEL_KEY)
    _add_sealed(tmp_path, "telegram", TelegramDetails(), TELEGRAM_TOKEN)

    listed = (await _listed(secrets, bots)).json()["credentials"]

    by_name = {c["name"]: c for c in listed}
    assert {name: c["details"]["kind"] for name, c in by_name.items()} == {
        "github": "custom",
        "trader_model": "llm",
        "telegram": "telegram",
    }
    assert by_name["github"]["last_four"] == "1234"
    assert by_name["trader_model"]["details"]["model"] == "big"
    assert by_name["telegram"]["last_four"] == "9012"


async def test_no_key_appears_in_full(
    tmp_path: Path, secrets: SecretService, bots: BotService
) -> None:
    secrets.save("github", GITHUB, SecretStr(GITHUB_KEY))
    _add_sealed(tmp_path, "telegram", TelegramDetails(), TELEGRAM_TOKEN)

    text = (await _listed(secrets, bots)).text

    assert GITHUB_KEY not in text
    assert TELEGRAM_TOKEN not in text


async def test_a_custom_key_lists_the_bots_allowed_to_use_it(
    secrets: SecretService, bots: BotService
) -> None:
    secrets.save("github", GITHUB, SecretStr(GITHUB_KEY))
    chef = await bots.create(BotDraft(name="Chef", instructions="Cook."))
    await bots.create(BotDraft(name="Trader", instructions="Trade."))
    bots.allow_secret(chef.id, "github")

    listed = (await _listed(secrets, bots)).json()["credentials"]

    assert listed[0]["bots"] == [{"id": chef.id, "name": "Chef"}]
