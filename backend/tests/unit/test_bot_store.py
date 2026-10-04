"""The bots file: read on every call, replaced whole, and Assistant always there."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID, Bot, BotNotFound, BotStore
from harness.session.models import BotInstructionsEvent
from harness.session.service import SessionService
from tests.unit.helpers import durable_service

KIND = Bot(id=ASSISTANT_ID, name="Assistant", instructions="Be kind.")


@pytest.fixture
def service(tmp_path: Path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def bots(tmp_path: Path, service: SessionService) -> BotStore:
    return BotStore(tmp_path / "bots.json", service, assistant_instructions="Be kind.")


def test_with_no_file_every_conversation_is_answered_by_assistant(
    tmp_path: Path, service: SessionService
) -> None:
    missing = BotStore(tmp_path / "no" / "bots.json", service, assistant_instructions="Be kind.")

    assert missing.bot_for("any-conversation") == KIND


async def test_listing_opens_assistant_s_chat_only_the_first_time(
    bots: BotStore, service: SessionService
) -> None:
    await bots.list()
    await bots.list()

    chat = await service.read(ASSISTANT_ID)
    assert list(chat.events()) == [BotInstructionsEvent(name="Assistant", instructions="Be kind.")]


def test_the_file_is_read_on_every_call(tmp_path: Path, bots: BotStore) -> None:
    assert bots.bot_for("r1") == KIND

    (tmp_path / "bots.json").write_text(
        json.dumps({"bots": [{"id": "r1", "name": "Researcher", "instructions": "Cite."}]})
    )

    assert bots.bot_for("r1") == Bot(id="r1", name="Researcher", instructions="Cite.")


async def test_a_failed_write_leaves_the_file_as_it_was(
    tmp_path: Path, bots: BotStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = await bots.create("Researcher", "Cite.")
    before = (tmp_path / "bots.json").read_text()

    def refuse(src: str, dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        bots.update(made.id, "Renamed", "Be brief.")

    assert (tmp_path / "bots.json").read_text() == before


def test_deleting_a_bot_nobody_made_is_refused(bots: BotStore) -> None:
    with pytest.raises(BotNotFound):
        bots.delete("nope")


async def test_a_deleted_bot_s_chat_is_answered_as_assistant(bots: BotStore) -> None:
    made = await bots.create("Researcher", "Cite.")

    bots.delete(made.id)

    assert bots.bot_for(made.id) == KIND


async def test_an_edited_assistant_stays_first_and_the_others_keep_their_order(
    bots: BotStore,
) -> None:
    first = await bots.create("First", "One.")
    second = await bots.create("Second", "Two.")

    bots.update(first.id, "First", "Uno.")
    bots.update(ASSISTANT_ID, "Helper", "Be terse.")

    assert await bots.list() == (
        Bot(id=ASSISTANT_ID, name="Helper", instructions="Be terse."),
        Bot(id=first.id, name="First", instructions="Uno."),
        second,
    )
