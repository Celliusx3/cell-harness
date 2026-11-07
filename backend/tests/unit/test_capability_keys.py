"""A capability key is a credential for one env variable of one MCP server."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from harness.secrets import Destination, DiskSecretRepository, SecretService
from harness.secrets.models.details import CapabilityDetails, TelegramDetails
from harness.secrets.models.errors import SecretRefused

KEY = "0123456789abcdef0123456789abcdef"
MAPS = CapabilityDetails(server="places", variable="GOOGLE_MAPS_API_KEY")


@pytest.fixture
def keyring(tmp_path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY)


def test_a_capability_key_reads_back_equal_and_sealed(tmp_path: Path, keyring) -> None:
    keyring.add_credential("maps", MAPS, SecretStr("AIza-maps-key-1234"))

    [saved] = SecretService(
        DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY
    ).saved_credentials()

    assert (saved.name, saved.details, saved.last_four) == ("maps", MAPS, "1234")
    assert "AIza-maps-key-1234" not in (tmp_path / "secrets.json").read_text()


def test_only_that_server_s_capability_keys_are_handed_out(keyring) -> None:
    keyring.add_credential("maps", MAPS, SecretStr("AIza-maps-key-1234"))
    coingecko = CapabilityDetails(server="markets", variable="COINGECKO_API_KEY")
    keyring.add_credential("coingecko", coingecko, SecretStr("CG-key-5678"))
    keyring.add_credential("telegram", TelegramDetails(), SecretStr("123:tg"))
    github = Destination(origin="https://api.github.com", auth="bearer")
    keyring.save("github", github, SecretStr("ghp-key-0001"))

    found = keyring.capability_keys("places")

    assert {name: value.get_secret_value() for name, value in found.items()} == {
        "GOOGLE_MAPS_API_KEY": "AIza-maps-key-1234"
    }
    assert keyring.capability_keys("nowhere") == {}


def test_a_second_key_for_the_same_variable_of_the_same_server_is_refused(keyring) -> None:
    keyring.add_credential("maps", MAPS, SecretStr("AIza-maps-key-1234"))

    with pytest.raises(SecretRefused, match="already saved as 'maps'"):
        keyring.add_credential("maps2", MAPS, SecretStr("AIza-other-key-9999"))


def test_a_capability_key_could_not_be_changed_onto_one_already_saved(keyring) -> None:
    keyring.add_credential("maps", MAPS, SecretStr("AIza-maps-key-1234"))
    other = CapabilityDetails(server="places", variable="OTHER_KEY")
    keyring.add_credential("other", other, SecretStr("other-key-0000"))

    with pytest.raises(SecretRefused, match="already saved as 'maps'"):
        keyring.change_credential("other", MAPS, None)
    keyring.change_credential("maps", MAPS, SecretStr("AIza-new-key-4321"))

    assert keyring.capability_keys("places")["GOOGLE_MAPS_API_KEY"].get_secret_value() == (
        "AIza-new-key-4321"
    )


@pytest.mark.parametrize(("server", "variable"), [("", "KEY"), ("places", "  ")])
def test_a_capability_key_names_its_server_and_variable(server: str, variable: str) -> None:
    with pytest.raises(ValidationError):
        CapabilityDetails(server=server, variable=variable)
