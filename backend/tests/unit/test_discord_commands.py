"""`/new` and `/stop` as Discord slash commands."""

from __future__ import annotations

import asyncio

from harness.channels.commands import CLEARED, NOTHING_TO_STOP, STOPPED, Command
from tests.unit.discord_fakes import FakeInteraction, build, message, settle
from tests.unit.fakes import HangingClient

CHAT = "77"


def test_exactly_the_four_commands_are_registered(tmp_path) -> None:
    channel = build(tmp_path)[0]

    assert {command.name for command in channel._tree.get_commands()} == {
        "new",
        "stop",
        "skills",
        "compact",
    }


async def test_skills_replies_with_the_list(tmp_path) -> None:
    channel, _, _, _, _, _ = build(tmp_path)
    interaction = FakeInteraction(CHAT)

    await channel._tree.get_command("skills").callback(interaction)

    assert interaction.replies == ["No skills installed. Commands: /new, /stop, /compact."]


async def test_new_clears_the_chat_in_place(tmp_path) -> None:
    channel, _, gateway, runs, chats, sessions = build(tmp_path)
    await channel.on_message(message(CHAT, "first"))
    await settle(gateway, runs)
    before = (await chats.load("discord", CHAT)).conversation_id

    interaction = FakeInteraction(CHAT)
    await channel._tree.get_command("new").callback(interaction)
    await channel.on_message(message(CHAT, "second"))
    await settle(gateway, runs)

    assert interaction.deferred
    assert interaction.replies == [CLEARED]
    assert (await chats.load("discord", CHAT)).conversation_id == before
    stored = await sessions.read(before)
    assert "chat/cleared" in [event.type for event in stored.events()]


async def test_stop_cancels_the_turn_and_clears_the_queue(tmp_path) -> None:
    channel, client, gateway, runs, chats, _ = build(tmp_path, HangingClient("partial"))
    chat = client.chat(CHAT)
    await channel.on_message(message(CHAT, "go"))
    run = runs.active((await chats.load("discord", CHAT)).conversation_id)
    while not any(e.type == "assistant/chunk" for e in run.session.events()):
        await asyncio.sleep(0.01)
    await channel.on_message(message(CHAT, "queued behind it"))

    interaction = FakeInteraction(CHAT)
    await channel._on_command(interaction, Command.STOP)
    await settle(gateway, runs)

    assert interaction.replies == [STOPPED]
    assert (await chats.load("discord", CHAT)).pending == ()
    assert chat.sent == ["partial"]


async def test_stop_with_nothing_running_says_so(tmp_path) -> None:
    channel = build(tmp_path)[0]
    interaction = FakeInteraction(CHAT)

    await channel._tree.get_command("stop").callback(interaction)

    assert interaction.replies == [NOTHING_TO_STOP]
