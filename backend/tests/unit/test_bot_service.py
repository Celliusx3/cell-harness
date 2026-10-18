"""The bots file: read on every call, replaced whole, and Assistant always there."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness.bots import (
    ASSISTANT_ID,
    BUILDER_ID,
    BUILDER_NAME,
    Bot,
    BotDraft,
    BotNotFound,
    BotPermanent,
    BotService,
    ChatMembers,
)
from harness.prompts import BUILDER_INSTRUCTIONS
from harness.session.models import BotInstructionsEvent
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from tests.unit.helpers import durable_service

KIND = Bot(id=ASSISTANT_ID, name="Assistant", instructions="Be kind.")
BUILDER = Bot(id=BUILDER_ID, name=BUILDER_NAME, instructions=BUILDER_INSTRUCTIONS)


@pytest.fixture
def service(tmp_path: Path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def bots(tmp_path: Path, service: SessionService) -> BotService:
    return BotService(tmp_path / "bots.json", service, assistant_instructions="Be kind.")


async def test_with_no_file_assistant_then_bot_builder_are_the_only_bots(
    tmp_path: Path, service: SessionService
) -> None:
    missing = BotService(tmp_path / "no" / "bots.json", service, assistant_instructions="Be kind.")

    assert await missing.active_bots() == (KIND, BUILDER)
    with pytest.raises(BotNotFound):
        missing.active_bot("any-conversation")


async def test_listing_opens_assistant_s_chat_only_the_first_time(
    bots: BotService, service: SessionService
) -> None:
    await bots.active_bots()
    await bots.active_bots()

    chat = await service.read(ASSISTANT_ID)
    assert list(chat.events()) == [
        BotInstructionsEvent(name="Assistant", instructions="Be kind.", bot_id=ASSISTANT_ID)
    ]


async def test_a_chat_belongs_to_the_bot_whose_chat_it_is(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))

    assert bots.members_of_chat("c0") == ChatMembers(group=None, bots=(made,))
    with pytest.raises(BotNotFound):
        bots.members_of_chat("c9")


async def test_a_bot_answers_in_the_chat_that_belongs_to_it(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))

    assert bots.members_of_chat(bots.chat_of(made.id)).bots == (made,)


def test_the_file_is_read_on_every_call(tmp_path: Path, bots: BotService) -> None:
    with pytest.raises(BotNotFound):
        bots.active_bot("r1")

    (tmp_path / "bots.json").write_text(
        json.dumps({"bots": [{"id": "r1", "name": "Researcher", "instructions": "Cite."}]})
    )

    assert bots.active_bot("r1") == Bot(id="r1", name="Researcher", instructions="Cite.")


async def test_a_failed_write_leaves_the_file_as_it_was(
    tmp_path: Path, bots: BotService, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))
    before = (tmp_path / "bots.json").read_text()

    def refuse(src: str, dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        bots.update(made.id, BotDraft(name="Renamed", instructions="Be brief."))

    assert (tmp_path / "bots.json").read_text() == before


async def test_deleting_a_bot_nobody_made_is_refused(bots: BotService) -> None:
    with pytest.raises(BotNotFound):
        await bots.delete("nope")


async def test_a_deleted_bot_owns_its_chat_no_more(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))

    await bots.delete(made.id)

    with pytest.raises(BotNotFound):
        bots.active_bot(made.id)


async def test_deleting_a_bot_removes_its_chat_for_good(
    tmp_path: Path, bots: BotService, service: SessionService
) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))
    bots.archive(made.id)

    await bots.delete(made.id)

    assert not (tmp_path / "sessions" / f"{made.id}.jsonl").exists()
    with pytest.raises(SessionNotFoundError):
        await service.read(made.id)
    assert bots.archived_bots() == ()


async def test_archiving_hides_a_bot_and_restoring_brings_it_back_as_it_was(
    bots: BotService, service: SessionService
) -> None:
    first = await bots.create(BotDraft(name="First", instructions="One."))
    second = await bots.create(BotDraft(name="Second", instructions="Two."))
    chat_before = list((await service.read(first.id)).events())

    bots.archive(second.id)
    bots.archive(first.id)

    assert await bots.active_bots() == (KIND, BUILDER)
    assert bots.archived_bots() == (
        first.model_copy(update={"archived": True}),
        second.model_copy(update={"archived": True}),
    )

    bots.restore(first.id)

    assert await bots.active_bots() == (KIND, BUILDER, first)
    assert list((await service.read(first.id)).events()) == chat_before


async def test_an_archived_bot_owns_no_chat_and_cannot_be_edited(bots: BotService) -> None:
    made = await bots.create(BotDraft(name="Researcher", instructions="Cite."))

    bots.archive(made.id)

    with pytest.raises(BotNotFound):
        bots.active_bot(made.id)
    with pytest.raises(BotNotFound):
        bots.update(made.id, BotDraft(name="Renamed", instructions="Be brief."))


def test_archiving_or_restoring_a_bot_nobody_made_is_refused(bots: BotService) -> None:
    with pytest.raises(BotNotFound):
        bots.archive("nope")
    with pytest.raises(BotNotFound):
        bots.restore("nope")


def test_restoring_assistant_leaves_it_as_it_was_and_writes_nothing(
    tmp_path: Path, bots: BotService
) -> None:
    bots.restore(ASSISTANT_ID)

    assert bots.active_bot(ASSISTANT_ID) == KIND
    assert not (tmp_path / "bots.json").exists()


async def test_assistant_can_be_neither_archived_nor_deleted(bots: BotService) -> None:
    with pytest.raises(BotPermanent):
        bots.archive(ASSISTANT_ID)
    with pytest.raises(BotPermanent):
        await bots.delete(ASSISTANT_ID)

    assert bots.active_bot(ASSISTANT_ID) == KIND


def test_a_bots_file_written_before_archiving_reads_every_bot_as_active(
    tmp_path: Path, bots: BotService
) -> None:
    (tmp_path / "bots.json").write_text(
        json.dumps({"bots": [{"id": "r1", "name": "Researcher", "instructions": "Cite."}]})
    )

    assert bots.active_bot("r1").archived is False
    assert bots.archived_bots() == ()


async def test_an_edited_assistant_stays_first_and_the_others_keep_their_order(
    bots: BotService,
) -> None:
    first = await bots.create(BotDraft(name="First", instructions="One."))
    second = await bots.create(BotDraft(name="Second", instructions="Two."))

    bots.update(first.id, BotDraft(name="First", instructions="Uno."))
    bots.update(ASSISTANT_ID, BotDraft(name="Helper", instructions="Be terse."))

    assert await bots.active_bots() == (
        Bot(id=ASSISTANT_ID, name="Helper", instructions="Be terse."),
        BUILDER,
        Bot(id=first.id, name="First", instructions="Uno."),
        second,
    )
