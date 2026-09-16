"""Stand-ins for PTB's bot and updates.

Faking at PTB's boundary rather than at HTTP: the library owns the wire now, and
a test that re-implemented Bot API JSON would be testing PTB rather than us. What
is ours is what we do with an `Update`, and what we ask the bot to send.
"""

from __future__ import annotations

from types import SimpleNamespace

from telegram import ReplyKeyboardRemove

from harness.channels.client import ChatAnswers
from harness.channels.gateway import ChannelGateway
from harness.channels.telegram.channel import TelegramChannel


class FakeBot:
    """Records what was sent. Stands in for PTB's `ExtBot`."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        # (chat, text, the inline keyboard) for every send that carried one.
        self.linked: list[tuple[str, str, object]] = []
        self.typing: list[str] = []
        # Set to raise on the next call, for the failure paths.
        self.fail_next: Exception | None = None
        # Set to refuse every send that carries a keyboard — Telegram's answer
        # to a URL it will not button.
        self.refuse_links: Exception | None = None

    async def send_message(
        self, chat_id: int, text: str, reply_markup: object = None, **_: object
    ) -> None:
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error
        # Every reply clears the keyboard; that is not a link, it is the
        # absence of one, and `sent` stays the list of plain replies.
        if isinstance(reply_markup, ReplyKeyboardRemove):
            reply_markup = None
        if reply_markup is not None and self.refuse_links is not None:
            raise self.refuse_links
        if reply_markup is not None:
            self.linked.append((str(chat_id), text, reply_markup))
        else:
            self.sent.append((str(chat_id), text))

    async def send_chat_action(self, chat_id: int, action: object, **_: object) -> None:
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error
        self.typing.append(str(chat_id))


def telegram_channel(
    gateway: ChannelGateway, locations: ChatAnswers | None = None
) -> tuple[TelegramChannel, FakeBot]:
    """A real `TelegramChannel` whose PTB bot is a fake.

    The channel itself is genuine — its batching, command handling and splitting
    are what the tests are for. Only the wire underneath is replaced, so PTB
    never dials api.telegram.org with a made-up token. `locations` is for the
    tests that send a pin; the rest never reach it.
    """
    channel = TelegramChannel("123:fake-token", gateway, locations or _no_locations())
    bot = FakeBot()
    channel._bot = bot  # type: ignore[assignment]
    return channel, bot


def _no_locations() -> ChatAnswers:
    """A resolver over nothing, for channels that will never receive a pin."""
    return ChatAnswers(None, None, None, None)  # type: ignore[arg-type]


def location_update(chat_id: str, latitude: float, longitude: float) -> SimpleNamespace:
    """A PTB `Update` carrying a pin — what tapping the share button sends."""
    pin = SimpleNamespace(latitude=latitude, longitude=longitude, horizontal_accuracy=None)
    return SimpleNamespace(
        effective_message=SimpleNamespace(text=None, location=pin, message_id=1),
        effective_chat=SimpleNamespace(id=int(chat_id)),
    )


def update(chat_id: str, text: str, message_id: int = 1) -> SimpleNamespace:
    """The shape of a PTB `Update` that the handler actually reads.

    A namespace rather than a real `Update`: constructing one needs a `Bot`
    attached for its methods to work, and the handler only touches
    `effective_message` and `effective_chat`.
    """
    message = SimpleNamespace(text=text, message_id=message_id)
    return SimpleNamespace(
        effective_message=message,
        effective_chat=SimpleNamespace(id=int(chat_id)),
    )
