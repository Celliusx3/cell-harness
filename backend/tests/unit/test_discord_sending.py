"""Sending to Discord: the 2000-character limit, and finding the chat."""

from __future__ import annotations

from types import SimpleNamespace

import discord

from harness.channels.discord.channel import MAX_MESSAGE_CHARS
from harness.channels.gateway import ChannelGateway
from tests.unit.discord_fakes import FakeMessageable, discord_channel
from tests.unit.helpers import no_skills


def _http_error(text: str) -> discord.HTTPException:
    return discord.HTTPException(SimpleNamespace(status=404, reason=text), text)


async def test_a_long_reply_is_split_within_the_limit() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    chat = client.chat("42")
    body = "word " * 1000

    await channel.send_message("42", body)

    sent = chat.sent
    assert len(sent) > 1
    assert all(len(part) <= MAX_MESSAGE_CHARS for part in sent)
    assert " ".join(sent).split() == body.split()


async def test_an_empty_reply_is_never_sent() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    chat = client.chat("42")

    await channel.send_message("42", "")

    assert chat.sent == []


async def test_an_uncached_chat_is_fetched() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    client.fetchable[42] = FakeMessageable()

    await channel.send_message("42", "hi")

    assert client.fetched == [42]
    assert client.fetchable[42].sent == ["hi"]


async def test_a_failed_send_is_not_swallowed() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    client.chat("42").fail_next = _http_error("unknown channel")

    try:
        await channel.send_message("42", "hi")
    except discord.HTTPException:
        return
    raise AssertionError("a failed send must propagate")


async def test_a_link_is_a_button_that_opens_the_page() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    chat = client.chat("42")

    await channel.send_link("42", "srv__show", "http://localhost:4897/apps/c0/c1")

    ((text, view),) = chat.linked
    (button,) = view.children
    assert text == "srv__show"
    assert isinstance(button, discord.ui.Button)
    assert (button.style, button.label, button.url) == (
        discord.ButtonStyle.link,
        "Open",
        "http://localhost:4897/apps/c0/c1",
    )
    assert chat.sent == []


async def test_typing_is_shown() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    chat = client.chat("42")

    await channel.send_typing("42")

    assert chat.typing_count == 1


async def test_a_failed_typing_indicator_is_swallowed() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    client.chat("42").fail_next = _http_error("unknown channel")

    await channel.send_typing("42")
