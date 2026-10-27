"""The keyring holds typed credentials, and every key saved before types existed reads as custom."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from harness.secrets import (
    DEFAULT_MODEL_CREDENTIAL,
    Destination,
    DiskSecretRepository,
    SecretService,
)
from harness.secrets.models.details import (
    CustomDetails,
    DiscordDetails,
    ModelDetails,
    TelegramDetails,
)
from harness.secrets.models.errors import SecretRefused
from harness.secrets.models.sealed import SealedSecret
from harness.secrets.sealing import sealed

KEY = "0123456789abcdef0123456789abcdef"
GITHUB = Destination(origin="https://api.github.com", auth="bearer")
TOKEN = "123456:AAfake-telegram-token"


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "secrets.json"


def _sealed(record_id: str, name: str, details, value: str) -> SealedSecret:
    return SealedSecret(
        id=record_id,
        name=name,
        details=details,
        ciphertext=sealed(value, encryption_key=KEY, record_id=record_id),
    )


def test_a_key_saved_before_types_existed_reads_as_custom(path: Path) -> None:
    record_id = "00ab"
    path.write_text(
        json.dumps(
            {
                "secrets": [
                    {
                        "id": record_id,
                        "name": "github",
                        "destination": {"origin": "https://api.github.com", "auth": "bearer"},
                        "ciphertext": sealed(
                            "ghp-old-key-1234", encryption_key=KEY, record_id=record_id
                        ),
                    }
                ]
            }
        )
    )

    store = SecretService(DiskSecretRepository(path), encryption_key=KEY)

    assert DiskSecretRepository(path).sealed_secrets()[0].details == CustomDetails(
        destination=GITHUB
    )
    found = store.secret_named("github")
    assert found is not None
    assert found.destination == GITHUB
    assert found.value.get_secret_value() == "ghp-old-key-1234"


def test_a_saved_custom_key_is_written_with_its_kind(path: Path) -> None:
    SecretService(DiskSecretRepository(path), encryption_key=KEY).save(
        "github", GITHUB, SecretStr("ghp-new-key-5678")
    )

    written = json.loads(path.read_text())["secrets"][0]
    assert written["details"]["kind"] == "custom"
    assert "ghp-new-key-5678" not in path.read_text()


def test_a_credential_of_each_kind_reads_back_equal(path: Path) -> None:
    entries = (
        _sealed("01", "github", CustomDetails(destination=GITHUB), "ghp-key-0001"),
        _sealed(
            "02",
            "trader_model",
            ModelDetails(base_url="https://api.example.com/v1", model="big-model"),
            "sk-model-0002",
        ),
        _sealed("03", "telegram", TelegramDetails(), TOKEN),
    )
    DiskSecretRepository(path).replace_all(entries)

    assert DiskSecretRepository(path).sealed_secrets() == entries
    assert TOKEN not in path.read_text()


def test_a_key_that_is_not_custom_is_never_handed_to_a_bot_fetch(path: Path) -> None:
    DiskSecretRepository(path).replace_all((_sealed("03", "telegram", TelegramDetails(), TOKEN),))

    assert (
        SecretService(DiskSecretRepository(path), encryption_key=KEY).secret_named("telegram")
        is None
    )


@pytest.mark.parametrize("name", ["github", "telegram", "absent"])
def test_a_turn_is_never_handed_a_key_that_is_not_a_model_credential(path: Path, name: str) -> None:
    DiskSecretRepository(path).replace_all(
        (
            _sealed("01", "github", CustomDetails(destination=GITHUB), "ghp-key-0001"),
            _sealed("03", "telegram", TelegramDetails(), TOKEN),
        )
    )
    store = SecretService(DiskSecretRepository(path), encryption_key=KEY)

    assert store.model_credential_version(name) is None
    assert store.model_credential_named(name) is None


def test_a_custom_key_cannot_take_the_name_of_another_kind(path: Path) -> None:
    DiskSecretRepository(path).replace_all((_sealed("03", "telegram", TelegramDetails(), TOKEN),))
    store = SecretService(DiskSecretRepository(path), encryption_key=KEY)

    with pytest.raises(SecretRefused):
        store.save("telegram", GITHUB, SecretStr("ghp-key-0009"))


def test_the_keys_list_holds_only_custom_keys(path: Path) -> None:
    DiskSecretRepository(path).replace_all(
        (
            _sealed("01", "github", CustomDetails(destination=GITHUB), "ghp-key-0001"),
            _sealed("03", "telegram", TelegramDetails(), TOKEN),
        )
    )

    names = [
        s.name for s in SecretService(DiskSecretRepository(path), encryption_key=KEY).summaries()
    ]

    assert names == ["github"]


def test_a_model_credential_needs_a_web_endpoint_and_a_model() -> None:
    with pytest.raises(ValueError):
        ModelDetails(base_url="ftp://example.com", model="m")
    with pytest.raises(ValueError):
        ModelDetails(base_url="https://api.example.com/v1", model="  ")


def test_the_default_model_cannot_be_removed_but_a_custom_key_of_its_name_can(path: Path) -> None:
    keyring = SecretService(DiskSecretRepository(path), encryption_key=KEY)
    keyring.save(DEFAULT_MODEL_CREDENTIAL, GITHUB, SecretStr("custom-key-5555"))
    keyring.delete(DEFAULT_MODEL_CREDENTIAL)
    default = ModelDetails(base_url="https://api.example.com/v1", model="glm")
    keyring.add_credential(DEFAULT_MODEL_CREDENTIAL, default, SecretStr("sk-default-key-1234"))

    with pytest.raises(SecretRefused, match="cannot be removed"):
        keyring.delete(DEFAULT_MODEL_CREDENTIAL)

    [saved] = keyring.saved_credentials()
    assert saved.is_default_model


def test_only_a_telegram_or_discord_credential_hands_out_its_token(path: Path) -> None:
    keyring = SecretService(DiskSecretRepository(path), encryption_key=KEY)
    keyring.save("telegram", GITHUB, SecretStr("custom-key-5555"))
    keyring.add_credential("chat_bot", DiscordDetails(), SecretStr("d-token-1234"))

    assert keyring.chat_platform_token("telegram") is None
    token = keyring.chat_platform_token("discord")
    assert token is not None and token.get_secret_value() == "d-token-1234"
