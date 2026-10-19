"""The keyring on disk: sealed keys replaced whole, owner-only, and a bad file never shown."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.secrets import Destination, DiskSecretRepository
from harness.secrets.models.sealed import SealedSecret

PLAINTEXT = "sk-live-PLAINTEXT-Q7xZ"
GITHUB = SealedSecret(
    id="00ab",
    name="github",
    destination=Destination(origin="https://api.github.com", auth="bearer"),
    ciphertext="c2VhbGVk",
)
NOTION = SealedSecret(
    id="00cd",
    name="notion",
    destination=Destination(origin="https://api.notion.com", auth="header", header_name="X-Key"),
    ciphertext="YWxzbyBzZWFsZWQ",
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "secrets.json"


def test_with_no_file_there_are_no_keys(path: Path) -> None:
    assert DiskSecretRepository(path).sealed_secrets() == ()


def test_keys_replaced_whole_read_back_equal(path: Path) -> None:
    disk = DiskSecretRepository(path)

    disk.replace_all((GITHUB, NOTION))
    disk.replace_all((NOTION,))

    assert disk.sealed_secrets() == (NOTION,)


def test_the_keyring_file_is_readable_by_its_owner_alone(path: Path) -> None:
    DiskSecretRepository(path).replace_all((GITHUB,))

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_the_keyring_folder_is_made_when_missing(tmp_path: Path) -> None:
    disk = DiskSecretRepository(tmp_path / "missing" / "secrets.json")

    disk.replace_all((GITHUB,))

    assert disk.sealed_secrets() == (GITHUB,)


def test_a_failed_write_keeps_the_saved_keys(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disk = DiskSecretRepository(path)
    disk.replace_all((GITHUB,))

    def refuse(source: str, target: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        disk.replace_all((GITHUB, NOTION))
    monkeypatch.undo()

    assert disk.sealed_secrets() == (GITHUB,)


@pytest.mark.parametrize(
    "content",
    [
        f"{PLAINTEXT} is not JSON",
        '{"secrets": [{"ciphertext": "' + PLAINTEXT,
        json.dumps({"secrets": PLAINTEXT}),
        json.dumps({"secrets": [], "note": PLAINTEXT}),
        json.dumps({"secrets": [{"id": PLAINTEXT, "ciphertext": PLAINTEXT}]}),
    ],
    ids=["not json", "cut short", "wrong shape", "unknown field", "broken entry"],
)
def test_a_malformed_secrets_file_raises_without_showing_its_content(
    path: Path, content: str
) -> None:
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValidationError) as raised:
        DiskSecretRepository(path).sealed_secrets()

    assert PLAINTEXT not in str(raised.value)
    assert PLAINTEXT not in repr(raised.value)
