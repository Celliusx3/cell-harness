"""The keyring: keys replaced, refused, capped, removed, listed, sealed, and never shown."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import SecretStr

from harness.secrets import (
    Destination,
    DiskSecretRepository,
    SecretNotFound,
    SecretRefused,
    SecretService,
    SecretSummary,
)

ENCRYPTION_KEY = "test-encryption-key"
KEY = "tok-9Zx=7Lm/q+Abc"
OTHER_KEY = "sk-live-Q7xZ-2468"
GITHUB = Destination(origin="https://api.github.com", auth="bearer")
NOTION = Destination(origin="https://api.notion.com", auth="bearer")
LINEAR = Destination(origin="https://api.linear.app", auth="bearer")
GITHUB_BY_HEADER = Destination(
    origin="https://api.github.com", auth="header", header_name="X-Api-Key"
)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "secrets.json"


@pytest.fixture
def store(path: Path) -> SecretService:
    return SecretService(DiskSecretRepository(path), encryption_key=ENCRYPTION_KEY)


def _raised(action: Callable[[], object]) -> Exception:
    try:
        action()
    except Exception as err:
        return err
    raise AssertionError("it did not raise")


def _shows(err: Exception, text: str) -> bool:
    return text in str(err) or text in repr(err)


def _entries(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["secrets"]


def _rewrite(path: Path, entries: list[dict]) -> None:
    whole = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**whole, "secrets": entries}), encoding="utf-8")


def _holding(store: SecretService, path: Path, count: int) -> None:
    store.save("github", GITHUB, SecretStr(KEY))
    (first,) = _entries(path)
    clones = [{**first, "id": os.urandom(12).hex(), "name": f"key_{n}"} for n in range(1, count)]
    _rewrite(path, [first, *clones])


def test_saving_a_name_again_for_the_same_site_replaces_the_key(
    store: SecretService, path: Path
) -> None:
    store.save("github", GITHUB, SecretStr(KEY))
    store.save("github", GITHUB, SecretStr(OTHER_KEY))

    found = store.find("github")
    assert found is not None
    assert found.value.get_secret_value() == OTHER_KEY
    assert len(_entries(path)) == 1


@pytest.mark.parametrize(
    "elsewhere",
    [
        Destination(origin="https://evil.example", auth="header", header_name="X-Api-Key"),
        Destination(origin="https://api.github.com", auth="bearer"),
        Destination(origin="https://api.github.com", auth="header", header_name="X-Other"),
    ],
    ids=["origin", "auth", "header"],
)
def test_a_name_saved_for_another_site_is_refused_without_showing_the_key(
    store: SecretService, elsewhere: Destination
) -> None:
    store.save("github", GITHUB_BY_HEADER, SecretStr(KEY))

    with pytest.raises(SecretRefused) as refused:
        store.save("github", elsewhere, SecretStr(OTHER_KEY))

    assert "already saved for https://api.github.com" in str(refused.value)
    assert not _shows(refused.value, OTHER_KEY)
    assert not _shows(refused.value, KEY)


def test_the_101st_key_is_refused_and_a_saved_one_can_still_be_replaced(
    store: SecretService, path: Path
) -> None:
    _holding(store, path, 99)
    store.save("notion", NOTION, SecretStr(KEY))

    with pytest.raises(SecretRefused):
        store.save("linear", LINEAR, SecretStr(KEY))
    store.save("notion", NOTION, SecretStr(OTHER_KEY))

    assert store.find("linear") is None
    found = store.find("notion")
    assert found is not None
    assert found.value.get_secret_value() == OTHER_KEY
    assert len(_entries(path)) == 100


def test_deleting_a_key_removes_it_and_leaves_the_others(store: SecretService) -> None:
    store.save("github", GITHUB, SecretStr(KEY))
    store.save("notion", NOTION, SecretStr(OTHER_KEY))

    store.delete("github")

    assert store.find("github") is None
    kept = store.find("notion")
    assert kept is not None
    assert kept.value.get_secret_value() == OTHER_KEY


def test_deleting_a_key_nobody_saved_is_refused_and_changes_nothing(
    store: SecretService, path: Path
) -> None:
    store.save("github", GITHUB, SecretStr(KEY))
    before = path.read_text(encoding="utf-8")

    with pytest.raises(SecretNotFound, match="'notion'"):
        store.delete("notion")

    assert path.read_text(encoding="utf-8") == before


def test_summaries_list_each_key_by_name_with_its_site_and_never_its_value(
    store: SecretService,
) -> None:
    store.save("notion", NOTION, SecretStr(OTHER_KEY))
    store.save("github", GITHUB, SecretStr(KEY))

    listed = store.summaries()

    assert listed == (
        SecretSummary(name="github", destination=GITHUB),
        SecretSummary(name="notion", destination=NOTION),
    )
    shown = repr(listed) + "".join(summary.model_dump_json() for summary in listed)
    assert KEY not in shown
    assert OTHER_KEY not in shown


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_encryption_key_is_refused(path: Path, blank: str) -> None:
    with pytest.raises(ValueError):
        SecretService(DiskSecretRepository(path), encryption_key=blank)


def test_a_file_sealed_under_one_encryption_key_does_not_open_under_another(
    store: SecretService, path: Path
) -> None:
    store.save("github", GITHUB, SecretStr(KEY))
    other = SecretService(DiskSecretRepository(path), encryption_key="another-encryption-key")

    err = _raised(lambda: other.find("github"))

    assert not _shows(err, KEY)


def test_a_sealed_key_copied_onto_another_entry_does_not_open(
    store: SecretService, path: Path
) -> None:
    store.save("github", GITHUB, SecretStr(KEY))
    store.save("notion", NOTION, SecretStr(OTHER_KEY))
    by_name = {entry["name"]: entry for entry in _entries(path)}
    moved = {**by_name["notion"], "ciphertext": by_name["github"]["ciphertext"]}
    _rewrite(path, [by_name["github"], moved])

    err = _raised(lambda: store.find("notion"))

    assert not _shows(err, KEY)
    assert not _shows(err, OTHER_KEY)
    still = store.find("github")
    assert still is not None
    assert still.value.get_secret_value() == KEY
