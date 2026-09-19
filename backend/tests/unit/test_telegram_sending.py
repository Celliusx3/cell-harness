"""Sending to Telegram: splitting, and the limits PTB does not handle for us."""

from __future__ import annotations

from telegram.error import BadRequest

from harness.channels.gateway import ChannelGateway
from harness.channels.telegram.channel import MAX_MESSAGE_CHARS
from harness.channels.text import split_message as split_at
from tests.unit.helpers import no_skills
from tests.unit.telegram_fakes import telegram_channel


def split_message(text: str) -> list[str]:
    """At Telegram's limit — the function itself is shared, the number is not."""
    return split_at(text, MAX_MESSAGE_CHARS)


def test_a_short_reply_is_one_message() -> None:
    assert split_message("hello") == ["hello"]


def test_a_long_reply_is_split_within_the_limit() -> None:
    parts = split_message("word " * 2000)

    assert len(parts) > 1
    assert all(len(part) <= MAX_MESSAGE_CHARS for part in parts)


def test_a_split_never_lands_mid_word() -> None:
    parts = split_message("word " * 2000)

    assert all(not part.startswith(" ") for part in parts)
    for part in parts[:-1]:
        assert part.endswith("d"), f"cut mid-word: {part[-20:]!r}"


def test_splitting_prefers_a_paragraph_break() -> None:
    body = ("a" * 3000) + "\n\n" + ("b" * 3000)

    assert split_message(body) == ["a" * 3000, "b" * 3000]


def test_text_with_no_break_at_all_still_splits() -> None:
    assert [len(part) for part in split_message("x" * 9000)] == [4096, 4096, 808]


def test_splitting_loses_no_words() -> None:
    body = "para one\n\n" + ("word " * 1500) + "\n\npara three"

    assert " ".join(split_message(body)).split() == body.split()


async def test_send_message_splits_over_the_wire() -> None:
    channel, bot = telegram_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )

    await channel.send_message("42", "word " * 2000)

    assert len(bot.sent) > 1
    assert all(chat_id == "42" for chat_id, _ in bot.sent)


async def test_an_empty_reply_is_never_sent() -> None:
    channel, bot = telegram_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )

    await channel.send_message("42", "")

    assert bot.sent == []


async def test_a_failed_typing_indicator_is_swallowed() -> None:
    channel, bot = telegram_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    bot.fail_next = BadRequest("chat not found")

    await channel.send_typing("42")


async def test_a_failed_send_is_not_swallowed() -> None:
    channel, bot = telegram_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    bot.fail_next = BadRequest("chat not found")

    try:
        await channel.send_message("42", "hi")
    except BadRequest:
        return
    raise AssertionError("a failed send must propagate")


async def test_an_https_link_opens_inside_telegram() -> None:
    channel, bot = telegram_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )

    await channel.send_link("42", "srv__show", "https://h.example/apps/c0/c1")

    ((chat_id, text, markup),) = bot.linked
    button = markup.inline_keyboard[0][0]
    assert (chat_id, text, button.text) == ("42", "srv__show", "Open")
    assert button.web_app.url == "https://h.example/apps/c0/c1"
    assert button.url is None


async def test_a_plain_http_link_opens_in_the_browser() -> None:
    channel, bot = telegram_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )

    await channel.send_link("42", "srv__show", "http://localhost:4897/apps/c0/c1")

    ((_, _, markup),) = bot.linked
    button = markup.inline_keyboard[0][0]
    assert button.url == "http://localhost:4897/apps/c0/c1"
    assert button.web_app is None


def test_the_transport_names_its_channel() -> None:
    assert (
        telegram_channel(ChannelGateway(None, None, None, no_skills(), public_url="http://t"))[
            0
        ].channel
        == "telegram"
    )
