"""Discord: a server @mention is the Assistant's, a DM is linked by a code or silent."""

from __future__ import annotations

from pathlib import Path

from harness.bots import ASSISTANT_ID
from harness.channels.commands import Command
from tests.unit.discord_fakes import BOT_ID, FakeInteraction, discord_channel, message
from tests.unit.link_helpers import World, prompts_in, world
from tests.webapp import idle

SERVER_CHANNEL = "300"
DM = "400"


def _discord(linked: World):
    channel, client = discord_channel(linked.gateway, linked.links)
    linked.gateway.register(channel)
    return channel, client


def _mention(text: str):
    return message(SERVER_CHANNEL, f"<@{BOT_ID}> {text}", guild=True, mentions=(BOT_ID,))


async def test_a_server_mention_reaches_the_assistant(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, client = _discord(linked)
    server_channel = client.chat(SERVER_CHANNEL)

    await channel.on_message(_mention("what is this?"))
    await idle(linked.runs, linked.gateway)

    assert await prompts_in(linked.sessions, ASSISTANT_ID) == ["what is this?"]
    assert server_channel.sent == ["hi"]
    stored = await linked.chats.load("discord", SERVER_CHANNEL)
    assert stored is not None and stored.conversation_id == ASSISTANT_ID


async def test_a_code_in_a_server_is_only_text_for_the_assistant(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, client = _discord(linked)
    code = linked.codes.issue(linked.chef.id, "discord")
    server_channel = client.chat(SERVER_CHANNEL)

    await channel.on_message(_mention(code.code))
    await idle(linked.runs, linked.gateway)

    assert await prompts_in(linked.sessions, ASSISTANT_ID) == [code.code]
    assert await prompts_in(linked.sessions, linked.chef.id) == []
    assert server_channel.sent == ["hi"]
    assert linked.codes.redeem("discord", DM, code.code) == linked.chef.id


async def test_a_dm_that_never_linked_gets_nothing(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, client = _discord(linked)
    dm = client.chat(DM)

    for text in ("hello", "/no-such-skill", "000000"):
        await channel.on_message(message(DM, text))
    await idle(linked.runs, linked.gateway)

    assert dm.sent == []
    assert await linked.chats.load("discord", DM) is None
    assert await prompts_in(linked.sessions, ASSISTANT_ID) == []


async def test_a_dm_sending_a_code_is_linked_and_talks_to_that_bot(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, client = _discord(linked)
    code = linked.codes.issue(linked.trader.id, "discord")
    dm = client.chat(DM)

    await channel.on_message(message(DM, code.code))
    await channel.on_message(message(DM, "buy low"))
    await idle(linked.runs, linked.gateway)

    assert dm.sent == ["Linked to Trader. Say hi.", "hi"]
    assert await prompts_in(linked.sessions, linked.trader.id) == ["buy low"]


async def test_an_unlinked_dms_slash_command_is_not_even_acknowledged(tmp_path: Path) -> None:
    linked = await world(tmp_path)
    channel, _ = _discord(linked)

    for command in Command:
        interaction = FakeInteraction(DM)
        await channel._on_command(interaction, command)
        assert (interaction.deferred, interaction.replies) == (False, [])
    assert await linked.chats.load("discord", DM) is None


def test_a_discord_chat_writes_nowhere_until_it_is_linked() -> None:
    channel, _ = discord_channel(None)

    assert channel.conversation_for(DM) == ""
