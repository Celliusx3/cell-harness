"""The bots file: read on every call, replaced whole, and Assistant always there."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID, Bot, BotNotFound, BotPermanent, BotService
from harness.session.models import BotInstructionsEvent
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from tests.unit.helpers import durable_service

KIND = Bot(id=ASSISTANT_ID, name="Assistant", instructions="Be kind.")


@pytest.fixture
def service(tmp_path: Path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def bots(tmp_path: Path, service: SessionService) -> BotService:
    return BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")


def test_with_no_file_assistant_is_the_only_bot(tmp_path: Path, service: SessionService) -> None:
    missing = BotService(tmp_path / "no" / "bots.json", service, assistant_instructions="Be kind.")

    assert missing.find(ASSISTANT_ID) == KIND
    with pytest.raises(BotNotFound):
        missing.find("any-conversation")


async def test_listing_opens_assistant_s_chat_only_the_first_time(
    bots: BotService, service: SessionService
) -> None:
    await bots.active_bots()
    await bots.active_bots()

    chat = await service.read(ASSISTANT_ID)
    assert list(chat.events()) == [BotInstructionsEvent(name="Assistant", instructions="Be kind.")]


def test_the_file_is_read_on_every_call(tmp_path: Path, bots: BotService) -> None:
    with pytest.raises(BotNotFound):
        bots.find("r1")

    (tmp_path / "bots.json").write_text(
        json.dumps({"bots": [{"id": "r1", "name": "Researcher", "instructions": "Cite."}]})
    )

    assert bots.find("r1") == Bot(id="r1", name="Researcher", instructions="Cite.")


async def test_a_failed_write_leaves_the_file_as_it_was(
    tmp_path: Path, bots: BotService, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = await bots.create("Researcher", "Cite.")
    before = (tmp_path / "bots.json").read_text()

    def refuse(src: str, dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        bots.update(made.id, "Renamed", "Be brief.")

    assert (tmp_path / "bots.json").read_text() == before


async def test_deleting_a_bot_nobody_made_is_refused(bots: BotService) -> None:
    with pytest.raises(BotNotFound):
        await bots.delete("nope")


async def test_a_deleted_bot_owns_its_chat_no_more(bots: BotService) -> None:
    made = await bots.create("Researcher", "Cite.")

    await bots.delete(made.id)

    with pytest.raises(BotNotFound):
        bots.find(made.id)


async def test_deleting_a_bot_removes_its_chat_for_good(
    tmp_path: Path, bots: BotService, service: SessionService
) -> None:
    made = await bots.create("Researcher", "Cite.")
    bots.archive(made.id)

    await bots.delete(made.id)

    assert not (tmp_path / "sessions" / f"{made.id}.jsonl").exists()
    with pytest.raises(SessionNotFoundError):
        await service.read(made.id)
    assert bots.archived_bots() == ()


async def test_archiving_hides_a_bot_and_restoring_brings_it_back_as_it_was(
    bots: BotService, service: SessionService
) -> None:
    first = await bots.create("First", "One.")
    second = await bots.create("Second", "Two.")
    chat_before = list((await service.read(first.id)).events())

    bots.archive(second.id)
    bots.archive(first.id)

    assert await bots.active_bots() == (KIND,)
    assert bots.archived_bots() == (
        first.model_copy(update={"archived": True}),
        second.model_copy(update={"archived": True}),
    )

    bots.restore(first.id)

    assert await bots.active_bots() == (KIND, first)
    assert list((await service.read(first.id)).events()) == chat_before


async def test_an_archived_bot_owns_no_chat_and_cannot_be_edited(bots: BotService) -> None:
    made = await bots.create("Researcher", "Cite.")

    bots.archive(made.id)

    with pytest.raises(BotNotFound):
        bots.find(made.id)
    with pytest.raises(BotNotFound):
        bots.update(made.id, "Renamed", "Be brief.")


def test_archiving_or_restoring_a_bot_nobody_made_is_refused(bots: BotService) -> None:
    with pytest.raises(BotNotFound):
        bots.archive("nope")
    with pytest.raises(BotNotFound):
        bots.restore("nope")


async def test_assistant_can_be_neither_archived_nor_deleted(bots: BotService) -> None:
    with pytest.raises(BotPermanent):
        bots.archive(ASSISTANT_ID)
    with pytest.raises(BotPermanent):
        await bots.delete(ASSISTANT_ID)

    assert bots.find(ASSISTANT_ID) == KIND


def test_a_bots_file_written_before_archiving_reads_every_bot_as_active(
    tmp_path: Path, bots: BotService
) -> None:
    (tmp_path / "bots.json").write_text(
        json.dumps({"bots": [{"id": "r1", "name": "Researcher", "instructions": "Cite."}]})
    )

    assert bots.find("r1").archived is False
    assert bots.archived_bots() == ()


async def test_an_edited_assistant_stays_first_and_the_others_keep_their_order(
    bots: BotService,
) -> None:
    first = await bots.create("First", "One.")
    second = await bots.create("Second", "Two.")

    bots.update(first.id, "First", "Uno.")
    bots.update(ASSISTANT_ID, "Helper", "Be terse.")

    assert await bots.active_bots() == (
        Bot(id=ASSISTANT_ID, name="Helper", instructions="Be terse."),
        Bot(id=first.id, name="First", instructions="Uno."),
        second,
    )
