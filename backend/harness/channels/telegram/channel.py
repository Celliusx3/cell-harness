"""Telegram, whole: receiving, sending, and the two limits it imposes.

**One object, because a platform is one thing.** Sending and receiving were
briefly separate classes here — `duta-ilmu` organises them that way — but the
receiving half *built* the sending half from its own PTB `Application`, so they
were one object pretending to be two and the wiring showed it.
`hermes-agent`'s `BasePlatformAdapter` covers connect, receive and send together,
and that is the shape this follows.

**Why `python-telegram-bot` rather than four `httpx` calls.** We had the four,
and they worked. What they did not have was rate limiting: Telegram allows
roughly 30 messages a second overall and about one a second per chat, and answers
a `429` with a `retry_after`. Our own client raised on that, delivery logged it,
and the reply was simply lost. PTB's `AIORateLimiter` queues instead. The library
costs one package, since it already shares our `httpx` and `anyio`.

**PTB owns the offset**, and that is the trade. Its updater advances the
acknowledgement when it *receives* a batch, before our handler runs — so a crash
mid-batch loses those messages rather than repeating them. Hermes ships that way;
`duta-ilmu` deliberately does the opposite. We gave up their at-least-once
semantics on purpose, for the rate limiting and the webhook and media surface
that come with the library.

**Batching, and why it is timers.** Telegram's *client* splits a long paste into
several messages, so without a buffer one paste is several turns — a correctness
bug, not a polish item, and the reason Hermes buffers at all:

    "Buffer rapid text messages so Telegram client-side splits of long messages
     are aggregated into a single MessageEvent."

A hand-rolled poller could not use per-chat timers, because the poll loop then had
to decide what to acknowledge while dispatches were still pending. With PTB
holding the offset that coupling is gone, and the delays below are Hermes's.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters

from harness.channels.commands import apply as apply_command
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage, OnMissing
from harness.channels.telegram import commands
from harness.channels.text import split_message

logger = logging.getLogger("harness.channels.telegram")

CHANNEL = "telegram"

# Telegram's hard cap on one message. Longer text is split — PTB does not split,
# it fails the send, and our own rules forbid truncating anything user-facing.
MAX_MESSAGE_CHARS = 4096

# Hermes's adaptive ingress delays, tuned for "feels instant". Short text reaches
# the model fast; only something long enough to have been client-split waits the
# full window.
FAST_LEN = 320
FAST_DELAY_SECONDS = 0.18
SHORT_LEN = 1024
SHORT_DELAY_SECONDS = 0.24
BATCH_DELAY_SECONDS = 0.30

# A message at or near the per-message limit was very likely cut by the client,
# so its continuation is worth waiting noticeably longer for.
SPLIT_SUSPECT_LEN = 4000
SPLIT_DELAY_SECONDS = 1.0

# What joins a batch: a newline, because that is how the lines were typed.
JOIN = "\n"

# The button under a message that links to an MCP App's page.
OPEN_LABEL = "Open"


def batch_delay(text: str) -> float:
    """How long to wait for the rest of `text`, if more is coming."""
    if len(text) >= SPLIT_SUSPECT_LEN:
        return SPLIT_DELAY_SECONDS
    if len(text) <= FAST_LEN:
        return FAST_DELAY_SECONDS
    if len(text) <= SHORT_LEN:
        return SHORT_DELAY_SECONDS
    return BATCH_DELAY_SECONDS


class _Batch:
    """Text accumulating for one chat, and the timer that will dispatch it."""

    __slots__ = ("text", "timer")

    def __init__(self, text: str, timer: asyncio.Task[None]) -> None:
        self.text = text
        self.timer = timer


class TelegramChannel:
    """`Channel` and `Pushing` for Telegram: receive, send, show typing.

    Satisfies both Protocols structurally — no base class, because that is what
    lets a platform live entirely in its own package.
    """

    channel = CHANNEL
    # A chat whose conversation vanished must keep working: the person holding the
    # phone has no address bar to correct and no way to start over except `/new`.
    # The browser is the opposite — it names the id it wants, so a miss is a 404.
    on_missing: OnMissing = "recreate"

    def __init__(self, token: str, gateway: ChannelGateway) -> None:
        self._gateway = gateway
        self._app: Application = (
            ApplicationBuilder().token(token).rate_limiter(_rate_limiter()).build()
        )
        # Held rather than reached through `self._app.bot` on every send. The
        # `Application` still owns its lifecycle; this is just the handle we use.
        self._bot = self._app.bot
        self._batches: dict[str, _Batch] = {}
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.UpdateType.EDITED, self._on))

    # ── receiving ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Poll until cancelled.

        `run_polling()` is deliberately not used: it installs signal handlers and
        owns the event loop, and this is a task inside a server that already
        does. The manual sequence is PTB's documented way to embed.
        """
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(
            # Only message-bearing updates. Telegram will otherwise send
            # reactions, join events and poll answers, none of which this phase
            # can map to a turn.
            allowed_updates=[Update.MESSAGE],
            # `False`: anything sent while the bot was down is answered when it
            # comes back, rather than silently dropped.
            drop_pending_updates=False,
        )
        try:
            # PTB runs its own tasks; this one just parks until cancelled so the
            # runtime has something to hold and cancel.
            await asyncio.Event().wait()
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        for batch in self._batches.values():
            batch.timer.cancel()
        self._batches.clear()
        if self._app.updater is not None and self._app.updater.running:
            await self._app.updater.stop()
        if self._app.running:
            await self._app.stop()
        await self._app.shutdown()

    async def _on(self, update: Update, _context: object) -> None:
        """One inbound message from PTB."""
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or not message.text:
            return
        chat_id = str(chat.id)
        text = message.text

        # Commands are never batched — `/stop` joined to the message after it
        # stops being a command at all. Parsed by Telegram's own rules, because
        # what counts as a command is a platform convention.
        command = commands.parse(text)
        if command is not None:
            await self._flush(chat_id)
            reply = await apply_command(self._gateway, CHANNEL, chat_id, command)
            await self.send_message(chat_id, reply)
            return

        existing = self._batches.pop(chat_id, None)
        if existing is not None:
            existing.timer.cancel()
            text = f"{existing.text}{JOIN}{text}"
        self._batches[chat_id] = _Batch(
            text=text,
            timer=asyncio.create_task(self._dispatch_after(chat_id, batch_delay(text))),
        )

    async def _dispatch_after(self, chat_id: str, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        await self._flush(chat_id)

    async def _flush(self, chat_id: str) -> None:
        """Hand one chat's accumulated text to the gateway, as one message."""
        batch = self._batches.pop(chat_id, None)
        if batch is None:
            return
        batch.timer.cancel()
        try:
            await self._gateway.receive(
                InboundMessage(channel=CHANNEL, chat_id=chat_id, text=batch.text)
            )
        except Exception:
            # One chat's bad message is not a reason to stop answering everyone
            # else, and PTB would otherwise route this to its error handlers.
            logger.exception("handling message from chat %s failed", chat_id)

    # ── sending ───────────────────────────────────────────────────────────────

    async def send_message(self, chat_id: str, text: str) -> None:
        """Send `text`, split across messages if it exceeds the limit.

        Plain text, deliberately. Telegram's MarkdownV2 requires escaping a dozen
        characters and rejects the *entire* message if one is missed — so a model
        writing a bare `!` or `.` in the wrong place would lose its whole answer.
        An unrendered asterisk is the cheaper failure.
        """
        for part in split_message(text, MAX_MESSAGE_CHARS):
            if part:
                await self._bot.send_message(chat_id=int(chat_id), text=part)

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        """One message with one button that opens `url`.

        A `web_app` button opens the page *inside* Telegram as a Mini App, which
        is what an MCP App wants — but Telegram accepts only `https://` there,
        so a plain-http dev URL gets a `url` button and opens in the browser
        instead. The choice is the platform's rule, not a fallback of ours.
        """
        if url.startswith("https://"):
            button = InlineKeyboardButton(OPEN_LABEL, web_app=WebAppInfo(url=url))
        else:
            button = InlineKeyboardButton(OPEN_LABEL, url=url)
        await self._bot.send_message(
            chat_id=int(chat_id), text=text, reply_markup=InlineKeyboardMarkup([[button]])
        )

    async def send_typing(self, chat_id: str) -> None:
        """Show "typing…" in the chat.

        Telegram clears it after about five seconds, so this is a heartbeat
        rather than a state to turn off. Best-effort by the Protocol's contract:
        a failed indicator must never stop a real reply from being sent.
        """
        try:
            await self._bot.send_chat_action(chat_id=int(chat_id), action=ChatAction.TYPING)
        except TelegramError as err:
            logger.debug("typing indicator failed for chat %s: %s", chat_id, err)


def _rate_limiter():
    """PTB's rate limiter, if the optional extra is installed.

    This is the reason for adopting the library at all, so its absence is worth a
    loud warning rather than a silent downgrade.
    """
    try:
        from telegram.ext import AIORateLimiter

        return AIORateLimiter()
    except ImportError:  # pragma: no cover - the extra is a declared dependency
        logger.warning(
            "python-telegram-bot's rate limiter is not installed; "
            "a burst of replies may be refused with 429"
        )
        return None
