"""Receiving from Telegram: batching, and commands jumping the queue."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from harness.agent.loop import LoopAgent
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.telegram.batching import (
    BATCH_DELAY_SECONDS,
    FAST_DELAY_SECONDS,
    SHORT_DELAY_SECONDS,
    SPLIT_DELAY_SECONDS,
    batch_delay,
)
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.skills import SkillService
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills, skills_at
from tests.unit.telegram_fakes import telegram_channel, update
from tests.unit.test_skill_tool import write_skill

CHAT = "77"


def build(tmp_path, *, skills: SkillService):
    ids = iter(f"c{n}" for n in range(100))
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        name="t", model="m", client=ScriptedClient(completed("ok")), checkpoint=sessions.flush
    )
    runs = RunStore(sessions, agent)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, skills, public_url="http://t")
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    return channel, bot, gateway, runs, chats, sessions


async def settle(gateway, runs) -> None:
    """Let the batch timer fire, then the turn and its delivery finish."""
    await asyncio.sleep(SPLIT_DELAY_SECONDS + 0.2)
    for _ in range(300):
        busy = gateway._tasks.running()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("channel never went idle")


async def prompts_of(sessions, chats) -> list[str]:
    state = await chats.load("telegram", CHAT)
    stored = await sessions.read(state.conversation_id)
    return [e.message.content for e in stored.events() if e.type == "user/message"]


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (10, FAST_DELAY_SECONDS),
        (320, FAST_DELAY_SECONDS),
        (900, SHORT_DELAY_SECONDS),
        (2000, BATCH_DELAY_SECONDS),
        (4100, SPLIT_DELAY_SECONDS),
    ],
)
def test_short_text_waits_less_than_a_suspected_split(length, expected) -> None:
    assert batch_delay("x" * length) == expected


async def test_a_client_split_paste_becomes_one_turn(tmp_path) -> None:
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=no_skills())

    await channel._on(update(CHAT, "first half of a paste", 1), None)
    await channel._on(update(CHAT, "second half", 2), None)
    await settle(gateway, runs)

    assert await prompts_of(sessions, chats) == ["first half of a paste\nsecond half"]


async def test_messages_far_apart_stay_separate_turns(tmp_path) -> None:
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=no_skills())

    await channel._on(update(CHAT, "first", 1), None)
    await settle(gateway, runs)
    await channel._on(update(CHAT, "second", 2), None)
    await settle(gateway, runs)

    assert await prompts_of(sessions, chats) == ["first", "second"]


async def test_different_chats_are_batched_separately(tmp_path) -> None:
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=no_skills())

    await channel._on(update("1", "to one", 1), None)
    await channel._on(update("2", "to two", 2), None)
    await settle(gateway, runs)

    assert sorted(bot.sent) == [("1", "ok"), ("2", "ok")]


async def test_a_command_is_answered_and_never_batched(tmp_path) -> None:
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=no_skills())

    await channel._on(update(CHAT, "/new", 1), None)

    assert bot.sent == [(CHAT, "New conversation started.")]


async def test_a_command_flushes_whatever_was_batching(tmp_path) -> None:
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=no_skills())
    handed: list[str] = []
    real = gateway.receive

    async def spy(message):
        handed.append(message.text)
        await real(message)

    gateway.receive = spy

    await channel._on(update(CHAT, "a question", 1), None)
    await channel._on(update(CHAT, "/stop", 2), None)
    await settle(gateway, runs)

    assert handed == ["a question"]


async def test_one_bad_message_does_not_stop_the_channel(tmp_path) -> None:
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=no_skills())

    async def boom(_message):
        raise RuntimeError("kaboom")

    gateway.receive = boom

    await channel._on(update(CHAT, "hello", 1), None)
    await asyncio.sleep(FAST_DELAY_SECONDS + 0.2)


async def test_an_update_with_no_text_is_ignored(tmp_path) -> None:
    from types import SimpleNamespace

    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=no_skills())
    empty = SimpleNamespace(effective_message=None, effective_chat=None)

    await channel._on(empty, None)

    assert bot.sent == []


async def test_a_skill_name_passes_through_and_is_expanded(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=skills_at(root))

    await channel._on(update(CHAT, "/find-place https://x"), None)
    await settle(gateway, runs)

    (content,) = await prompts_of(sessions, chats)
    assert content.startswith('/find-place https://x\n\n<skill name="find-place">')
    assert bot.sent == [(CHAT, "ok")]


async def test_an_unknown_skill_name_is_answered_not_sent_to_the_model(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    channel, bot, gateway, runs, chats, sessions = build(tmp_path, skills=skills_at(root))

    await channel._on(update(CHAT, "/start"), None)
    await settle(gateway, runs)

    assert bot.sent == [
        (CHAT, "No skill named 'start'. Skills: /find-place. Commands: /new, /stop, /compact.")
    ]
    assert await chats.load("telegram", CHAT) is None
