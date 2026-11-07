"""On start, the settings file's keys move into the keyring once, and the file keeps the rest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.config.sections import LLMSettings, SecretSettings
from harness.config.settings import Settings
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.models.details import ModelDetails
from harness.web.file_keys import MODEL_CREDENTIAL, move_file_keys
from harness.web.server import build_keyring

KEY = "0123456789abcdef0123456789abcdef"
MODEL_KEY = "sk-file-model-key-1234"
TELEGRAM_TOKEN = "123456:AAfile-telegram-5678"
DISCORD_TOKEN = "discord-file-token-9012"
LLM = LLMSettings(model="glm", base_url="https://api.example.com/v1")
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
    model = saved[MODEL_CREDENTIAL]
    assert model.details == ModelDetails(base_url=LLM.base_url, model=LLM.model, vision=False)
    assert (saved["telegram"].details.kind, saved["discord"].details.kind) == (
        "telegram",
        "discord",
    )
    assert [saved[name].last_four for name in (MODEL_CREDENTIAL, "telegram", "discord")] == [
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
    edited = ModelDetails(base_url="https://other.example/v1", model="edited", vision=False)
    keyring.change_credential(MODEL_CREDENTIAL, edited, None)

    _write(local_json, {"llm": {"api_key": "sk-rotated-key-4321"}})
    move_file_keys(local_json, LLM, keyring)

    model = _saved(keyring)[MODEL_CREDENTIAL]
    assert (model.last_four, model.details) == ("4321", edited)


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


def _start_settings(tmp_path: Path, local_json: Path) -> Settings:
    secrets = SecretSettings(path=tmp_path / "secrets.json", encryption_key=KEY)
    return Settings.model_construct(llm=LLM, secrets=secrets, local_settings_path=local_json)


def test_with_no_model_key_the_harness_still_starts(tmp_path: Path, local_json) -> None:
    keyring = build_keyring(_start_settings(tmp_path, local_json))

    assert keyring.model_credential_version(MODEL_CREDENTIAL) is None


def test_a_model_key_in_the_file_becomes_an_llm_credential_at_start(
    tmp_path: Path, local_json
) -> None:
    _write(local_json, ALL_KEYS)

    keyring = build_keyring(_start_settings(tmp_path, local_json))

    assert keyring.model_credential_version(MODEL_CREDENTIAL) is not None
