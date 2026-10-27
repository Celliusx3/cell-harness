"""On start, the settings file's keys move into the keyring once, and the file keeps the rest."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from harness.bots import BotService
from harness.config.sections import LLMSettings
from harness.config.settings import MissingConfigError
from harness.secrets import DEFAULT_MODEL_CREDENTIAL, DiskSecretRepository, SecretService
from harness.secrets.models.details import ModelDetails
from harness.web.file_keys import move_file_keys, require_default_model
from harness.web.routes.credentials import build_router
from tests.unit.helpers import durable_service

KEY = "0123456789abcdef0123456789abcdef"
MODEL_KEY = "sk-file-model-key-1234"
TELEGRAM_TOKEN = "123456:AAfile-telegram-5678"
DISCORD_TOKEN = "discord-file-token-9012"
LLM = LLMSettings(model="glm", vision=True, base_url="https://api.example.com/v1")
ALL_KEYS = {
    "llm": {"api_key": MODEL_KEY, "temperature": 0.5},
    "telegram": {"bot_token": TELEGRAM_TOKEN},
    "discord": {"bot_token": DISCORD_TOKEN},
    "secrets": {"encryption_key": KEY},
}


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
    path.chmod(0o600)


def _saved(keyring: SecretService) -> dict:
    return {credential.name: credential for credential in keyring.saved_credentials()}


@pytest.fixture
def local_json(tmp_path: Path) -> Path:
    return tmp_path / "config.local.json"


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


def test_every_key_in_the_file_becomes_a_credential(local_json, keyring) -> None:
    _write(local_json, ALL_KEYS)

    move_file_keys(local_json, LLM, keyring)

    saved = _saved(keyring)
    default = saved[DEFAULT_MODEL_CREDENTIAL]
    assert default.details == ModelDetails(base_url=LLM.base_url, model=LLM.model)
    assert (saved["telegram"].details.kind, saved["discord"].details.kind) == (
        "telegram",
        "discord",
    )
    assert [
        saved[name].last_four for name in (DEFAULT_MODEL_CREDENTIAL, "telegram", "discord")
    ] == [
        "1234",
        "5678",
        "9012",
    ]


def test_the_file_keeps_every_other_value_and_no_key(local_json, keyring) -> None:
    _write(local_json, ALL_KEYS)

    move_file_keys(local_json, LLM, keyring)

    text = local_json.read_text(encoding="utf-8")
    assert all(key not in text for key in (MODEL_KEY, TELEGRAM_TOKEN, DISCORD_TOKEN))
    assert json.loads(text) == {"llm": {"temperature": 0.5}, "secrets": {"encryption_key": KEY}}
    assert local_json.stat().st_mode & 0o777 == 0o600


def test_a_second_start_moves_nothing(tmp_path: Path, local_json, keyring) -> None:
    _write(local_json, ALL_KEYS)
    move_file_keys(local_json, LLM, keyring)
    file_before = local_json.read_text(encoding="utf-8")
    keyring_before = (tmp_path / "secrets.json").read_text(encoding="utf-8")

    move_file_keys(local_json, LLM, keyring)

    assert local_json.read_text(encoding="utf-8") == file_before
    assert (tmp_path / "secrets.json").read_text(encoding="utf-8") == keyring_before


def test_a_key_put_back_in_the_file_replaces_only_the_saved_key(local_json, keyring) -> None:
    _write(local_json, ALL_KEYS)
    move_file_keys(local_json, LLM, keyring)
    edited = ModelDetails(base_url="https://other.example/v1", model="edited")
    keyring.change_credential(DEFAULT_MODEL_CREDENTIAL, edited, None)

    _write(local_json, {"llm": {"api_key": "sk-rotated-key-4321"}})
    move_file_keys(local_json, LLM, keyring)

    default = _saved(keyring)[DEFAULT_MODEL_CREDENTIAL]
    assert (default.last_four, default.details) == ("4321", edited)


def test_a_file_with_no_keys_is_left_alone(local_json, keyring) -> None:
    _write(local_json, {"secrets": {"encryption_key": KEY}})
    before = local_json.read_text(encoding="utf-8")

    move_file_keys(local_json, LLM, keyring)

    assert keyring.saved_credentials() == ()
    assert local_json.read_text(encoding="utf-8") == before


def test_a_missing_file_is_left_alone(tmp_path: Path, keyring) -> None:
    absent = tmp_path / "absent.json"

    move_file_keys(absent, LLM, keyring)

    assert keyring.saved_credentials() == ()
    assert not absent.exists()


def test_with_no_default_model_the_harness_refuses_to_start(local_json, keyring) -> None:
    with pytest.raises(MissingConfigError, match="api_key") as refused:
        require_default_model(keyring, local_json)

    assert str(local_json) in str(refused.value)


def test_with_a_default_model_it_starts(local_json, keyring) -> None:
    _write(local_json, ALL_KEYS)
    move_file_keys(local_json, LLM, keyring)

    require_default_model(keyring, local_json)


async def test_the_default_model_cannot_be_removed(tmp_path: Path, local_json, keyring) -> None:
    _write(local_json, ALL_KEYS)
    move_file_keys(local_json, LLM, keyring)
    bots = BotService(
        tmp_path / "bots.json", durable_service(tmp_path / "s"), assistant_instructions=""
    )
    app = FastAPI()
    app.include_router(build_router(keyring, bots))
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))

    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4886") as http:
        response = await http.delete(
            f"/api/credentials/{DEFAULT_MODEL_CREDENTIAL}",
            headers={"origin": "http://127.0.0.1:4887"},
        )

    assert response.status_code == 409
    assert DEFAULT_MODEL_CREDENTIAL in _saved(keyring)
