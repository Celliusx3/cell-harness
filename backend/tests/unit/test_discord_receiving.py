"""What the Discord channel does with a message: who it answers, and how.

The handler is driven directly, as the Telegram tests drive theirs — the
library's websocket is never opened.
"""

from __future__ import annotations

import logging

from tests.unit.discord_fakes import BOT_ID, build, message, settle

CHAT = "77"


async def prompts_of(sessions, chats, chat_id: str = CHAT) -> list[str]:
    state = await chats.load("discord", chat_id)
    stored = await sessions.read(state.conversation_id)
    return [e.message.content for e in stored.events() if e.type == "user/message"]


async def test_a_dm_becomes_a_turn_and_a_reply(tmp_path) -> None:
    channel, client, gateway, runs, chats, sessions = build(tmp_path)
    chat = client.chat(CHAT)

    await channel.on_message(message(CHAT, "hello"))
    await settle(gateway, runs)

    assert await prompts_of(sessions, chats) == ["hello"]
    assert chat.sent == ["ok"]


async def test_a_guild_message_without_a_mention_is_ignored(tmp_path) -> None:
    """The bot reads what is addressed to it and nothing else."""
    channel, client, gateway, runs, chats, _ = build(tmp_path)

    await channel.on_message(message(CHAT, "hello everyone", guild=True))
    await settle(gateway, runs)

    assert await chats.load("discord", CHAT) is None
    assert client.chat(CHAT).sent == []


async def test_a_mention_is_answered_with_the_mention_stripped(tmp_path) -> None:
    channel, client, gateway, runs, chats, sessions = build(tmp_path)
    chat = client.chat(CHAT)

    await channel.on_message(
        message(CHAT, f"<@{BOT_ID}> what is this?", guild=True, mentions=(BOT_ID,))
    )
    await settle(gateway, runs)

    assert await prompts_of(sessions, chats) == ["what is this?"]
    assert chat.sent == ["ok"]


async def test_the_legacy_nickname_mention_is_stripped_too(tmp_path) -> None:
    channel, _, gateway, runs, chats, sessions = build(tmp_path)

    await channel.on_message(message(CHAT, f"hi <@!{BOT_ID}>", guild=True, mentions=(BOT_ID,)))
    await settle(gateway, runs)

    assert await prompts_of(sessions, chats) == ["hi"]


async def test_a_mention_of_someone_else_is_not_for_us(tmp_path) -> None:
    channel, _, gateway, runs, chats, _ = build(tmp_path)

    await channel.on_message(message(CHAT, "<@123> hey", guild=True, mentions=(123,)))
    await settle(gateway, runs)

    assert await chats.load("discord", CHAT) is None


async def test_a_bare_ping_is_not_a_prompt(tmp_path) -> None:
    channel, _, gateway, runs, chats, _ = build(tmp_path)

    await channel.on_message(message(CHAT, f"<@{BOT_ID}>", guild=True, mentions=(BOT_ID,)))
    await settle(gateway, runs)

    assert await chats.load("discord", CHAT) is None


async def test_a_bot_author_is_ignored(tmp_path) -> None:
    """Discord delivers the bot's own sends back; two bots answering each other
    never stop. The one guard this channel has."""
    channel, _, gateway, runs, chats, _ = build(tmp_path)

    await channel.on_message(message(CHAT, "ok", bot=True))
    await settle(gateway, runs)

    assert await chats.load("discord", CHAT) is None


async def test_each_channel_or_thread_is_its_own_conversation(tmp_path) -> None:
    channel, _, gateway, runs, chats, _ = build(tmp_path)

    await channel.on_message(message("1", "one"))
    await settle(gateway, runs)
    await channel.on_message(message("2", "two"))
    await settle(gateway, runs)

    first = await chats.load("discord", "1")
    second = await chats.load("discord", "2")
    assert first.conversation_id != second.conversation_id


async def test_a_gateway_failure_is_logged_not_raised(tmp_path, caplog) -> None:
    """The library would otherwise route it to `on_error` and keep going; we
    say what happened rather than letting one chat's message vanish silently."""
    channel, _, gateway, runs, _, _ = build(tmp_path)

    async def explode(_message):
        raise RuntimeError("disk on fire")

    gateway.receive = explode  # type: ignore[method-assign]

    with caplog.at_level(logging.ERROR, logger="harness.channels.discord"):
        await channel.on_message(message(CHAT, "hello"))  # must not raise

    assert "disk on fire" in caplog.text


def test_the_transport_names_its_channel(tmp_path) -> None:
    """Part of a chat's identity, so Telegram `123` and Discord `123` differ."""
    assert build(tmp_path)[0].channel == "discord"
    assert build(tmp_path)[0].on_missing == "recreate"


async def test_an_unknown_skill_name_is_answered_not_sent_to_the_model(tmp_path) -> None:
    """Discord hands an unregistered `/word` over as plain text; the gateway
    decides, and the reply is the same one Telegram gives."""
    channel, client, gateway, runs, chats, sessions = build(tmp_path)
    chat = client.chat(CHAT)

    await channel.on_message(message(CHAT, "/summarise this"))
    await settle(gateway, runs)

    assert chat.sent == [
        "No skill named 'summarise'. Skills: none. Commands: /new, /stop, /compact."
    ]
    assert await chats.load("discord", CHAT) is None
