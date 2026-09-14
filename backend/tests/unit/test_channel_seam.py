"""A third platform, to prove the seam holds.

`FakeWhatsApp` implements `Channel` and nothing else — no Telegram import, no
shared base class, and **no change to `gateway.py`, `commands.py` or
`repository.py`**. If adding it had required touching any of those, the seam
would be in the wrong place and this file is where that shows up.

Two platforms is also when an interface earns its keep, which is the project's
own rule for building one at all — and this is the third, standing in for the
WhatsApp that has not been written yet. (It was `FakeWhatsApp` until a real
`DiscordChannel` arrived and made the name a trap.)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from harness.agent.loop import LoopAgent
from harness.channels.commands import Command, apply
from harness.channels.gateway import (
    ChannelGateway,
    DuplicateChannelError,
    UnknownChannelError,
)
from harness.channels.protocol import InboundMessage
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.telegram_fakes import telegram_channel

WHATSAPP = "whatsapp"


class FakeWhatsApp:
    """A whole platform in 20 lines.

    Deliberately unlike Telegram where it can be: no message splitting (the
    limit differs), and **no typing indicator at all** — the Protocol says a
    platform without the idea implements it as a no-op, and this is the test of
    that claim.
    """

    channel = WHATSAPP
    on_missing = "recreate"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.ran = False

    async def run(self) -> None:
        self.ran = True
        await asyncio.Event().wait()

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    async def send_typing(self, chat_id: str) -> None:
        return None

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        # No buttons here: the URL travels as text, which every platform can carry.
        self.sent.append((chat_id, f"{text}\n{url}"))


def build(tmp_path):
    ids = iter(f"c{n}" for n in range(100))
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        name="t",
        model="m",
        client=ScriptedClient(completed("answered")),
        checkpoint=sessions.flush,
    )
    runs = RunStore(sessions, agent)
    chats = JsonlChatRepository(tmp_path / "chats")
    return ChannelGateway(chats, runs, sessions, public_url="http://t"), runs, chats


async def settle(runs, gateway, key) -> None:
    for _ in range(300):
        task = gateway._following.get(key)
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("gateway never went idle")


def message(chat_id: str, text: str) -> InboundMessage:
    return InboundMessage(channel=WHATSAPP, chat_id=chat_id, text=text)


async def test_a_second_platform_needs_no_shared_changes(tmp_path) -> None:
    """The whole point: register a new `Channel`, everything else already works."""
    gateway, runs, _ = build(tmp_path)
    whatsapp = FakeWhatsApp()
    gateway.register(whatsapp)

    await gateway.receive(message("guild-1", "hello"))
    await settle(runs, gateway, (WHATSAPP, "guild-1"))

    assert whatsapp.sent == [("guild-1", "answered")]


async def test_commands_work_on_any_platform(tmp_path) -> None:
    """The *actions* are shared; only recognising them is per-platform.

    A Discord bot triggers this from an interactions payload and a WhatsApp one
    from a keyword — neither goes near Telegram's leading slash, which is why
    parsing lives in the platform and only `apply` is here.
    """
    gateway, runs, chats = build(tmp_path)
    gateway.register(FakeWhatsApp())
    await gateway.receive(message("guild-1", "hello"))
    await settle(runs, gateway, (WHATSAPP, "guild-1"))
    assert (await chats.load(WHATSAPP, "guild-1")).conversation_id != ""

    reply = await apply(gateway, WHATSAPP, "guild-1", Command.NEW)

    assert "New conversation" in reply
    assert (await chats.load(WHATSAPP, "guild-1")).conversation_id == ""


async def test_a_platform_with_no_typing_indicator_is_fine(tmp_path) -> None:
    """The Protocol allows a no-op, so email or SMS can satisfy it."""
    gateway, runs, _ = build(tmp_path)
    whatsapp = FakeWhatsApp()
    gateway.register(whatsapp)

    await gateway.receive(message("guild-1", "hello"))
    await settle(runs, gateway, (WHATSAPP, "guild-1"))

    assert whatsapp.sent == [("guild-1", "answered")]


# ── two platforms at once ─────────────────────────────────────────────────────


async def test_two_platforms_share_one_gateway(tmp_path) -> None:
    """**The reason the gateway is singular.**

    Both platforms run through the same rules, the same chat store and the same
    run store — and each reply goes back out the way it came in, chosen by
    `InboundMessage.channel`.
    """
    gateway, runs, _ = build(tmp_path)
    whatsapp = FakeWhatsApp()
    telegram, telegram_bot = telegram_channel(gateway)
    gateway.register(whatsapp)
    gateway.register(telegram)

    await gateway.receive(InboundMessage(channel=WHATSAPP, chat_id="9", text="from whatsapp"))
    await settle(runs, gateway, (WHATSAPP, "9"))
    await gateway.receive(InboundMessage(channel="telegram", chat_id="9", text="from telegram"))
    await settle(runs, gateway, ("telegram", "9"))

    assert whatsapp.sent == [("9", "answered")]
    assert telegram_bot.sent == [("9", "answered")]


async def test_the_same_chat_id_on_two_platforms_stays_separate(tmp_path) -> None:
    """Telegram chat `9` and WhatsApp chat `9` are different conversations,
    which is why the channel is part of a chat's identity."""
    gateway, runs, chats = build(tmp_path)
    whatsapp = FakeWhatsApp()
    telegram, _ = telegram_channel(gateway)
    gateway.register(whatsapp)
    gateway.register(telegram)

    await gateway.receive(InboundMessage(channel=WHATSAPP, chat_id="9", text="a"))
    await settle(runs, gateway, (WHATSAPP, "9"))
    await gateway.receive(InboundMessage(channel="telegram", chat_id="9", text="b"))
    await settle(runs, gateway, ("telegram", "9"))

    whatsapp_state = await chats.load(WHATSAPP, "9")
    telegram_state = await chats.load("telegram", "9")
    assert whatsapp_state.conversation_id != telegram_state.conversation_id


async def test_a_message_from_an_unregistered_platform_is_loud(tmp_path) -> None:
    """A channel wired to receive but not to reply reads every message and
    answers none — so it fails rather than going quiet."""
    gateway, _, _ = build(tmp_path)

    try:
        await gateway.receive(message("guild-1", "hello"))
    except UnknownChannelError:
        return
    raise AssertionError("an unregistered channel must not be ignored")


# ── the registry itself ───────────────────────────────────────────────────────


async def test_registering_a_platform_twice_is_refused(tmp_path) -> None:
    """Two registrations used to give one transport and *two* listeners, because
    a dict overwrote while a list appended. Two pollers on one bot token is a
    409 from Telegram, so the disagreement had to go — and registering twice is
    a wiring mistake, not something to resolve silently."""
    gateway, _, _ = build(tmp_path)
    gateway.register(FakeWhatsApp())

    try:
        gateway.register(FakeWhatsApp())
    except DuplicateChannelError:
        return
    raise AssertionError("a second registration must not be accepted")


async def test_a_finished_delivery_is_forgotten(tmp_path) -> None:
    """Otherwise every chat that ever got a reply leaves a completed task behind
    until the process stops — unbounded, keyed by chat."""
    gateway, runs, _ = build(tmp_path)
    gateway.register(FakeWhatsApp())

    await gateway.receive(message("guild-1", "hello"))
    await settle(runs, gateway, (WHATSAPP, "guild-1"))
    # The callback runs on the loop's next pass, not inline with the task ending.
    await asyncio.sleep(0)

    assert gateway._following == {}
