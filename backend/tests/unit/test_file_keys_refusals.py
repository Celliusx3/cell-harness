"""The move never loses a key: a key it cannot seal stays in the file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from harness.config.sections import LLMSettings
from harness.config.settings import MissingConfigError
from harness.secrets import (
    DEFAULT_MODEL_CREDENTIAL,
    Destination,
    DiskSecretRepository,
    SecretService,
)
from harness.secrets.models.details import TelegramDetails
from harness.web.file_keys import move_file_keys

KEY = "0123456789abcdef0123456789abcdef"
MODEL_KEY = "sk-file-model-key-1234"
LLM = LLMSettings(model="glm", vision=True, base_url="https://api.example.com/v1")
SITE = Destination(origin="https://api.example.com", auth="bearer")


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
    path.chmod(0o600)


@pytest.fixture
def local_json(tmp_path: Path) -> Path:
    return tmp_path / "config.local.json"


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_key_moves_nothing_and_leaves_the_file_alone(local_json, keyring, blank) -> None:
    _write(local_json, {"llm": {"api_key": blank}, "telegram": {"bot_token": blank}})
    before = local_json.read_bytes()

    move_file_keys(local_json, LLM, keyring)

    assert keyring.saved_credentials() == ()
    assert local_json.read_bytes() == before


def test_a_name_taken_by_another_kind_refuses_and_the_key_stays(local_json, keyring) -> None:
    keyring.save(DEFAULT_MODEL_CREDENTIAL, SITE, SecretStr("custom-key-5555"))
    _write(local_json, {"llm": {"api_key": MODEL_KEY}})

    with pytest.raises(MissingConfigError, match=DEFAULT_MODEL_CREDENTIAL) as refused:
        move_file_keys(local_json, LLM, keyring)

    assert "stays in the file" in str(refused.value)
    assert MODEL_KEY not in str(refused.value)
    assert json.loads(local_json.read_text())["llm"]["api_key"] == MODEL_KEY


def test_a_key_the_keyring_fails_to_seal_stays_in_the_file(
    local_json, keyring, monkeypatch
) -> None:
    _write(local_json, {"llm": {"api_key": MODEL_KEY}, "discord": {"bot_token": "d-token-1234"}})

    def failing_seal(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(keyring, "add_or_replace_key", failing_seal)

    with pytest.raises(OSError, match="disk full"):
        move_file_keys(local_json, LLM, keyring)

    assert json.loads(local_json.read_text())["llm"]["api_key"] == MODEL_KEY


def test_a_key_that_is_not_text_is_refused_without_echoing_the_file(local_json, keyring) -> None:
    _write(local_json, {"llm": {"api_key": 1234}, "telegram": {"bot_token": "t-secret-9876"}})

    with pytest.raises(ValidationError) as refused:
        move_file_keys(local_json, LLM, keyring)

    assert "t-secret-9876" not in str(refused.value)
    assert keyring.saved_credentials() == ()


def test_only_a_section_the_move_empties_is_dropped(local_json, keyring) -> None:
    _write(local_json, {"discord": {"bot_token": "d-token-1234"}, "mcp": {}, "note": "kept"})

    move_file_keys(local_json, LLM, keyring)

    assert json.loads(local_json.read_text()) == {"mcp": {}, "note": "kept"}


def test_no_temp_file_is_left_beside_the_settings_file(tmp_path, local_json, keyring) -> None:
    _write(local_json, {"llm": {"api_key": MODEL_KEY}})

    move_file_keys(local_json, LLM, keyring)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["config.local.json", "secrets.json"]


def test_a_saved_token_of_the_same_kind_is_replaced_in_place(local_json, keyring) -> None:
    keyring.add_credential("telegram", TelegramDetails(), SecretStr("t-old-token-1111"))
    _write(local_json, {"telegram": {"bot_token": "t-new-token-2222"}})

    move_file_keys(local_json, LLM, keyring)

    [saved] = keyring.saved_credentials()
    assert (saved.name, saved.last_four) == ("telegram", "2222")
