"""Telegram hears private chats only, a code links one to a bot, and an unlinked one is silent."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID
from harness.channels.client import ChatAnswers
from tests.unit.helpers import client_tools
from tests.unit.link_helpers import World, prompts_in, world
from tests.unit.telegram_fakes import (
    FakeBot,
    decision_update,
    location_update,
    telegram_channel,
    update,
)
from tests.webapp import idle

GATEWAY_ENTRIES = ("receive", "clear", "stop", "compact_chat", "is_linked", "resume")


def _telegram(linked: World):
    answers = ChatAnswers(linked.chats, linked.sessions, linked.gateway, client_tools())
    channel, bot = telegram_channel(linked.gateway, answers, linked.links)
    linked.gateway.register(channel)
    return channel, bot


async def _says(channel, chat_id: str, text: str, chat_type: str = "private") -> None:
    """One message from `chat_id`, handed over at once."""
    await channel._on(update(chat_id, text, chat_type=chat_type), None)
    await channel._flush(chat_id)


def _refuse_every_gateway_entry(linked: World) -> None:
    def never(*_args, **_kwargs):
        raise AssertionError("the gateway was handed a group's traffic")

    for name in GATEWAY_ENTRIES:
        setattr(linked.gateway, name, never)


def _nothing_sent(bot: FakeBot) -> bool:
    return bot.sent == [] and bot.linked == [] and bot.typing == []


@pytest.mark.parametrize("chat_type", ["group", "supergroup"])
async def test_a_group_text_or_command_gets_no_reply_and_never_reaches_the_gateway(
    tmp_path: Path, chat_type: str
) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)
    code = linked.codes.issue(linked.chef.id, "telegram")
    _refuse_every_gateway_entry(linked)

    for text in ("hello", "/new", "/stop@my_bot", "/skills", code.code):
        await _says(channel, "-100", text, chat_type)

    assert _nothing_sent(bot)
    assert await linked.chats.load("telegram", "-100") is None


async def test_a_group_location_or_tap_never_reaches_the_gateway(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)
    _refuse_every_gateway_entry(linked)
    tap = decision_update("-100", "ap:c1:once", "Allow?", chat_type="group")

    await channel._on_location(location_update("-100", 1.3, 103.8, chat_type="group"), None)
    await channel._on_decision(tap, None)

    assert _nothing_sent(bot)
    assert not tap.callback_query.answered


async def test_a_private_chat_sending_a_code_is_linked_and_talks_to_that_bot(
    tmp_path: Path,
) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)
    code = linked.codes.issue(linked.chef.id, "telegram")

    await _says(channel, "1", code.code)
    await _says(channel, "1", "what is for dinner?")
    await idle(linked.runs, linked.gateway)

    assert bot.sent == [("1", "Linked to Chef. Say hi."), ("1", "hi")]
    assert await prompts_in(linked.sessions, linked.chef.id) == ["what is for dinner?"]
    assert await prompts_in(linked.sessions, ASSISTANT_ID) == []


async def test_an_unlinked_private_new_sends_nothing_and_changes_nothing(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)

    for command in ("/new", "/stop", "/compact", "/skills"):
        await _says(channel, "1", command)

    assert _nothing_sent(bot)
    assert await linked.chats.load("telegram", "1") is None
    assert await prompts_in(linked.sessions, ASSISTANT_ID) == []


async def test_an_unlinked_private_chat_gets_no_answer_at_all(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)

    for text in ("hello", "/start", "/no-such-skill", "000000"):
        await _says(channel, "1", text)
    await channel._on_location(location_update("1", 1.3, 103.8), None)
    await idle(linked.runs, linked.gateway)

    assert _nothing_sent(bot)
    assert await linked.chats.load("telegram", "1") is None
    assert linked.runs.active(ASSISTANT_ID) is None


async def test_a_strangers_traffic_is_logged_at_debug_only(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    linked = await world(tmp_path)
    channel, _ = _telegram(linked)
    caplog.set_level(logging.DEBUG, logger="harness")

    for text in ("hello", "/new", *["000000"] * 6):
        await _says(channel, "1", text)
    await _says(channel, "-100", "hello", "group")

    said = [record for record in caplog.records if record.name.startswith("harness.channels")]
    assert said and all(record.levelno == logging.DEBUG for record in said)


async def test_an_unlinked_private_tap_is_not_even_answered(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, bot = _telegram(linked)
    tap = decision_update("1", "ap:c1:once", "Allow?")

    await channel._on_decision(tap, None)

    assert not tap.callback_query.answered
    assert tap.callback_query.edits == []
    assert _nothing_sent(bot)


def test_a_telegram_chat_writes_nowhere_until_it_is_linked(tmp_path: Path) -> None:
    channel, _ = telegram_channel(None)

    assert channel.conversation_for("1") == ""
