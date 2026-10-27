"""A chat stored before codes talks to Assistant; one a code linked, to its bot or nobody."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID
from harness.channels.client import ChatAnswers
from harness.channels.repository import ChatState
from tests.unit.discord_fakes import discord_channel, message
from tests.unit.helpers import client_tools
from tests.unit.link_helpers import World, prompts_in, world
from tests.unit.telegram_fakes import telegram_channel, update
from tests.webapp import idle

CHAT = "1"
OLD_CHAT = "an-old-chat"


def _telegram(linked: World):
    answers = ChatAnswers(linked.chats, linked.sessions, linked.gateway, client_tools())
    channel, bot = telegram_channel(linked.gateway, answers, linked.links)
    linked.gateway.register(channel)
    return channel, bot


async def _says(linked: World, channel, text: str) -> None:
    await channel._on(update(CHAT, text), None)
    await channel._flush(CHAT)
    await idle(linked.runs, linked.gateway)


async def _linked_to_chef(linked: World, channel) -> None:
    await _says(linked, channel, linked.codes.issue(linked.chef.id, "telegram").code)


def _loud(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno > logging.DEBUG]


async def test_a_telegram_chat_stored_under_an_old_id_reaches_assistant(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)
    await linked.chats.save(ChatState(channel="telegram", chat_id=CHAT, conversation_id=OLD_CHAT))

    await _says(linked, channel, "still here")

    assert await prompts_in(linked.sessions, ASSISTANT_ID) == ["still here"]
    assert bot.sent == [(CHAT, "hi")]


async def test_a_discord_dm_stored_under_an_old_id_reaches_assistant(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, client = discord_channel(linked.gateway, linked.links)
    linked.gateway.register(channel)
    dm = client.chat(CHAT)
    await linked.chats.save(ChatState(channel="discord", chat_id=CHAT, conversation_id=OLD_CHAT))

    await channel.on_message(message(CHAT, "still here"))
    await idle(linked.runs, linked.gateway)

    assert await prompts_in(linked.sessions, ASSISTANT_ID) == ["still here"]
    assert dm.sent == ["hi"]


async def test_a_chat_linked_to_an_archived_bot_is_silent_until_it_is_restored(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)
    await _linked_to_chef(linked, channel)
    linked.bots.archive(linked.chef.id)
    caplog.set_level(logging.DEBUG, logger="harness")

    for text in ("anyone there?", "/new", "/stop"):
        await _says(linked, channel, text)
    silent = list(bot.sent)
    loud = _loud(caplog)
    linked.bots.restore(linked.chef.id)
    await _says(linked, channel, "back again")

    assert silent == [(CHAT, "Linked to Chef. Say hi.")]
    assert loud == []
    assert bot.sent[-1] == (CHAT, "hi")
    assert await prompts_in(linked.sessions, linked.chef.id) == ["back again"]
    assert await prompts_in(linked.sessions, ASSISTANT_ID) == []


async def test_a_chat_linked_to_a_deleted_bot_is_silent_and_never_reaches_assistant(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)
    await _linked_to_chef(linked, channel)
    linked.bots.archive(linked.chef.id)
    await linked.bots.delete(linked.chef.id)
    caplog.set_level(logging.DEBUG, logger="harness")

    for text in ("anyone there?", "/new", "/compact"):
        await _says(linked, channel, text)

    assert bot.sent == [(CHAT, "Linked to Chef. Say hi.")]
    assert _loud(caplog) == []
    assert list((tmp_path / "sessions").glob(f"{linked.chef.id}*")) == []
    assert await prompts_in(linked.sessions, ASSISTANT_ID) == []
    stored = await linked.chats.load("telegram", CHAT)
    assert stored is not None and stored.linked_bot_id == linked.chef.id


async def test_a_strangers_first_message_is_still_silent(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)

    await _says(linked, channel, "hello?")

    assert bot.sent == []
    assert await linked.chats.load("telegram", CHAT) is None
    assert list((tmp_path / "sessions").glob(f"{ASSISTANT_ID}*")) == []
