"""Sending to Telegram: splitting, and the limits PTB does not handle for us."""

from __future__ import annotations

from telegram.error import BadRequest

from harness.channels.gateway import ChannelGateway
from harness.channels.telegram.channel import MAX_MESSAGE_CHARS, split_message
from tests.unit.telegram_fakes import telegram_channel

# ── splitting, which stays ours ───────────────────────────────────────────────


def test_a_short_reply_is_one_message() -> None:
    assert split_message("hello") == ["hello"]


def test_a_long_reply_is_split_within_the_limit() -> None:
    parts = split_message("word " * 2000)

    assert len(parts) > 1
    assert all(len(part) <= MAX_MESSAGE_CHARS for part in parts)


def test_a_split_never_lands_mid_word() -> None:
    """PTB does not split at all — it fails the send. A hard cut at 4096 is
    visibly broken, so it is our last resort rather than our implementation."""
    parts = split_message("word " * 2000)

    assert all(not part.startswith(" ") for part in parts)
    for part in parts[:-1]:
        assert part.endswith("d"), f"cut mid-word: {part[-20:]!r}"


def test_splitting_prefers_a_paragraph_break() -> None:
    body = ("a" * 3000) + "\n\n" + ("b" * 3000)

    assert split_message(body) == ["a" * 3000, "b" * 3000]


def test_text_with_no_break_at_all_still_splits() -> None:
    """A pasted token or base64 blob has nowhere natural to cut."""
    assert [len(part) for part in split_message("x" * 9000)] == [4096, 4096, 808]


def test_splitting_loses_no_words() -> None:
    """Our rules forbid truncating anything user-facing.

    Asserted on words rather than characters: the split trims whitespace at each
    boundary, which is the point — a message should not begin with the space the
    cut landed on.
    """
    body = "para one\n\n" + ("word " * 1500) + "\n\npara three"

    assert " ".join(split_message(body)).split() == body.split()


# ── sending ───────────────────────────────────────────────────────────────────


async def test_send_message_splits_over_the_wire() -> None:
    channel, bot = telegram_channel(ChannelGateway(None, None, None))

    await channel.send_message("42", "word " * 2000)

    assert len(bot.sent) > 1
    assert all(chat_id == "42" for chat_id, _ in bot.sent)


async def test_an_empty_reply_is_never_sent() -> None:
    """Telegram rejects an empty message, and it says nothing anyway."""
    channel, bot = telegram_channel(ChannelGateway(None, None, None))

    await channel.send_message("42", "")

    assert bot.sent == []


async def test_a_failed_typing_indicator_is_swallowed() -> None:
    """The Protocol calls it best-effort: a real reply must not be lost to it."""
    channel, bot = telegram_channel(ChannelGateway(None, None, None))
    bot.fail_next = BadRequest("chat not found")

    await channel.send_typing("42")  # must not raise


async def test_a_failed_send_is_not_swallowed() -> None:
    """Unlike typing. Delivery must know it failed, or the cursor would advance
    past a reply that never arrived."""
    channel, bot = telegram_channel(ChannelGateway(None, None, None))
    bot.fail_next = BadRequest("chat not found")

    try:
        await channel.send_message("42", "hi")
    except BadRequest:
        return
    raise AssertionError("a failed send must propagate")


def test_the_transport_names_its_channel() -> None:
    """Part of a chat's identity, so Telegram `123` and Discord `123` differ."""
    assert telegram_channel(ChannelGateway(None, None, None))[0].channel == "telegram"
