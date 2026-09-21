"""Stand-ins for PTB's bot and updates."""

from __future__ import annotations

from types import SimpleNamespace

from telegram import ReplyKeyboardRemove

from harness.channels.client import ChatAnswers
from harness.channels.gateway import ChannelGateway
from harness.channels.telegram.channel import TelegramChannel
from tests.unit.helpers import client_tools


class FakeBot:
    """Records what was sent. Stands in for PTB's `ExtBot`."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.linked: list[tuple[str, str, object]] = []
        self.typing: list[str] = []
        self.fail_next: Exception | None = None
        self.refuse_links: Exception | None = None

    async def send_message(
        self, chat_id: int, text: str, reply_markup: object = None, **_: object
    ) -> None:
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error
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
    """A real `TelegramChannel` whose PTB bot is a fake."""
    channel = TelegramChannel("123:fake-token", gateway, locations or _no_locations())
    bot = FakeBot()
    channel._bot = bot
    return channel, bot


def _no_locations() -> ChatAnswers:
    """A resolver over nothing, for channels that will never receive a pin."""
    return ChatAnswers(None, None, None, client_tools())


def location_update(chat_id: str, latitude: float, longitude: float) -> SimpleNamespace:
    """A PTB `Update` carrying a pin — what tapping the share button sends."""
    pin = SimpleNamespace(latitude=latitude, longitude=longitude, horizontal_accuracy=None)
    return SimpleNamespace(
        effective_message=SimpleNamespace(text=None, location=pin, message_id=1),
        effective_chat=SimpleNamespace(id=int(chat_id)),
    )


def update(chat_id: str, text: str, message_id: int = 1) -> SimpleNamespace:
    """The shape of a PTB `Update` that the handler actually reads."""
    message = SimpleNamespace(text=text, message_id=message_id)
    return SimpleNamespace(
        effective_message=message,
        effective_chat=SimpleNamespace(id=int(chat_id)),
    )


class FakeCallbackQuery:
    """What a tap on an inline button hands the handler."""

    def __init__(self, chat_id: str, data: str, card_text: str) -> None:
        self.data = data
        self.message = SimpleNamespace(text=card_text, chat=SimpleNamespace(id=int(chat_id)))
        self.answered = False
        self.edits: list[tuple[str, object]] = []

    async def answer(self, **_: object) -> None:
        self.answered = True

    async def edit_message_text(self, text: str, reply_markup: object = None, **_: object) -> None:
        self.edits.append((text, reply_markup))


def decision_update(chat_id: str, data: str, card_text: str) -> SimpleNamespace:
    """A PTB `Update` carrying a callback query — what tapping Allow or Deny sends."""
    return SimpleNamespace(
        callback_query=FakeCallbackQuery(chat_id, data, card_text),
        effective_chat=SimpleNamespace(id=int(chat_id)),
        effective_message=None,
    )
