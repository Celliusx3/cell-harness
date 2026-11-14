"""The bots repository: one bot fetched or changed at a time, in one file."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID, Bot, BotNotFound, BotRepository

ASSISTANT = Bot(id=ASSISTANT_ID, name="Assistant", instructions="Be kind.")
RESEARCHER = Bot(id="r1", name="Researcher", instructions="Find sources.")
WRITER = Bot(id="w1", name="Writer", instructions="Write it up.")


def repository_holding(tmp_path: Path, *bots: Bot) -> BotRepository:
    repository = BotRepository(tmp_path / "bots.json")
    for bot in bots:
        repository.add(bot)
    return repository


def test_a_missing_file_holds_no_bots(tmp_path: Path) -> None:
    repository = BotRepository(tmp_path / "no" / "bots.json")

    assert repository.bots() == ()


def test_an_added_bot_goes_last(tmp_path: Path) -> None:
    repository = repository_holding(tmp_path, WRITER)

    repository.add(RESEARCHER)

    assert repository.bots() == (WRITER, RESEARCHER)


def test_an_updated_bot_replaces_the_stored_one_in_its_place(tmp_path: Path) -> None:
    repository = repository_holding(tmp_path, RESEARCHER, WRITER)
    renamed = RESEARCHER.model_copy(update={"name": "Scout"})

    repository.update(renamed)

    assert repository.bots() == (renamed, WRITER)


def test_an_updated_bot_that_is_not_stored_yet_goes_first(tmp_path: Path) -> None:
    repository = repository_holding(tmp_path, WRITER)

    repository.update(ASSISTANT, RESEARCHER)

    assert repository.bots() == (ASSISTANT, RESEARCHER, WRITER)


def test_updating_several_bots_replaces_and_adds_with_one_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = repository_holding(tmp_path, RESEARCHER, WRITER)
    renamed = WRITER.model_copy(update={"name": "Editor"})
    replace_file = os.replace
    written: list[Path] = []

    def replace_and_count(source: str, target: Path) -> None:
        written.append(target)
        replace_file(source, target)

    monkeypatch.setattr(os, "replace", replace_and_count)
    repository.update(renamed, ASSISTANT)

    assert repository.bots() == (ASSISTANT, RESEARCHER, renamed)
    assert written == [tmp_path / "bots.json"]


def test_updating_no_bot_leaves_the_stored_bots_as_they_were(tmp_path: Path) -> None:
    repository = repository_holding(tmp_path, WRITER, RESEARCHER)

    repository.update()

    assert repository.bots() == (WRITER, RESEARCHER)


def test_an_archived_bot_is_found(tmp_path: Path) -> None:
    archived = RESEARCHER.model_copy(update={"archived": True})
    repository = repository_holding(tmp_path, WRITER, archived)

    assert repository.find("r1") == archived


def test_finding_a_bot_that_is_not_stored_is_refused(tmp_path: Path) -> None:
    repository = repository_holding(tmp_path, WRITER)

    with pytest.raises(BotNotFound):
        repository.find("r1")


def test_deleting_a_bot_leaves_the_rest_in_order(tmp_path: Path) -> None:
    repository = repository_holding(tmp_path, WRITER, RESEARCHER, ASSISTANT)

    repository.delete("r1")

    assert repository.bots() == (WRITER, ASSISTANT)


def test_deleting_a_bot_that_is_not_stored_changes_nothing(tmp_path: Path) -> None:
    repository = repository_holding(tmp_path, WRITER, RESEARCHER)

    repository.delete("nope")

    assert repository.bots() == (WRITER, RESEARCHER)


def test_a_second_repository_on_the_same_path_reads_what_the_first_wrote(tmp_path: Path) -> None:
    repository_holding(tmp_path, WRITER)

    second = BotRepository(tmp_path / "bots.json")

    assert second.bots() == (WRITER,)
