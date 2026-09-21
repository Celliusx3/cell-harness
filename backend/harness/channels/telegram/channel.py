"""Telegram, whole: receiving, sending, and the two limits it imposes."""

from __future__ import annotations

import asyncio
import logging
from typing import NamedTuple

from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from harness.channels.client import ChatAnswers
from harness.channels.commands import apply as apply_command
from harness.channels.commands import unknown_skill
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage, OnMissing
from harness.channels.telegram import commands
from harness.channels.telegram.asking import BUTTONS, CALLBACK_PREFIX, MAX_MESSAGE_CHARS, ask_client
from harness.channels.telegram.batching import JOIN, Batch, batch_delay
from harness.channels.text import split_message
from harness.skills import UnknownSkill
from harness.tools.client import PendingCall
from harness.tools.native.location import LOCATION

logger = logging.getLogger("harness.channels.telegram")

CHANNEL = "telegram"

OPEN_LABEL = "Open"

RECEIPTS: dict[str, str] = {
    "once": "✅ Allowed once",
    "conversation": "✅ Allowed for this conversation",
    "always": "✅ Always allowed",
    "deny": "❌ Denied",
}
STALE_TAP = "This request was already answered."
CHOICES = frozenset(choice for _, choice in BUTTONS)


class TelegramChannel:
    """`Channel` and `Pushing` for Telegram: receive, send, show typing."""

    channel = CHANNEL
    on_missing: OnMissing = "recreate"

    def __init__(self, token: str, gateway: ChannelGateway, answers: ChatAnswers) -> None:
        self._gateway = gateway
        self._answers = answers
        self._app: Application = (
            ApplicationBuilder().token(token).rate_limiter(AIORateLimiter()).build()
        )
        self._bot = self._app.bot
        self._batches: dict[str, Batch] = {}
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.UpdateType.EDITED, self._on))
        self._app.add_handler(MessageHandler(filters.LOCATION, self._on_location))
        self._app.add_handler(
            CallbackQueryHandler(self._on_decision, pattern=rf"^{CALLBACK_PREFIX}:")
        )

    async def run(self) -> None:
        """Poll until cancelled."""
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(
            allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY],
            drop_pending_updates=False,
        )
        try:
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
        self._batches[chat_id] = Batch(
            text=text,
            timer=asyncio.create_task(self._dispatch_after(chat_id, batch_delay(text))),
        )

    async def _on_location(self, update: Update, _context: object) -> None:
        """A location: the answer to a pending `get_location`, else a message as text."""
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or message.location is None:
            return
        chat_id = str(chat.id)
        pin = message.location
        shared = {
            "kind": "shared",
            "data": {
                "latitude": pin.latitude,
                "longitude": pin.longitude,
                "accuracy_m": pin.horizontal_accuracy or 0.0,
            },
        }
        if await self._answers.answer(self, chat_id, LOCATION, shared):
            return
        await self._flush(chat_id)
        text = f"(shared location: {pin.latitude}, {pin.longitude})"
        await self._gateway.receive(InboundMessage(channel=CHANNEL, chat_id=chat_id, text=text))

    async def _on_decision(self, update: Update, _context: object) -> None:
        """A tap on Allow or Deny: answer the pending call, then turn the card into a receipt."""
        query = update.callback_query
        chat = update.effective_chat
        if query is None or chat is None:
            return
        await query.answer()
        tap = _parse_tap(query.data)
        if tap is None:
            logger.warning("chat %s tapped a button with unreadable data %r", chat.id, query.data)
            await self._edit_card(query, STALE_TAP)
            return
        body = (
            {"kind": "denied"}
            if tap.choice == "deny"
            else {"kind": "approved", "scope": tap.choice}
        )
        ok = await self._answers.answer_call(self, str(chat.id), tap.call_id, body)
        await self._edit_card(query, RECEIPTS[tap.choice] if ok else STALE_TAP)

    async def _edit_card(self, query: CallbackQuery, receipt: str) -> None:
        try:
            await query.edit_message_text(f"{query.message.text}\n\n{receipt}", reply_markup=None)
        except TelegramError as err:
            logger.debug("editing the approval card failed: %s", err)

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
        except UnknownSkill as err:
            await self.send_message(
                chat_id, unknown_skill(err.name, self._gateway.skills.invocable())
            )
        except Exception:
            logger.exception("handling message from chat %s failed", chat_id)

    async def send_message(self, chat_id: str, text: str) -> None:
        """Send `text`, split across messages if it exceeds the limit."""
        for part in split_message(text, MAX_MESSAGE_CHARS):
            if part:
                await self._bot.send_message(
                    chat_id=int(chat_id), text=part, reply_markup=ReplyKeyboardRemove()
                )

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        """One message with one button that opens `url`."""
        if url.startswith("https://"):
            button = InlineKeyboardButton(OPEN_LABEL, web_app=WebAppInfo(url=url))
        else:
            button = InlineKeyboardButton(OPEN_LABEL, url=url)
        await self._bot.send_message(
            chat_id=int(chat_id), text=text, reply_markup=InlineKeyboardMarkup([[button]])
        )

    async def ask_client(self, chat_id: str, request: PendingCall, url: str) -> None:
        """Telegram's own prompt where it has one, the page otherwise — `asking.py`."""
        await ask_client(self, self._bot, chat_id, request, url, gated=self._answers.gated)

    async def send_typing(self, chat_id: str) -> None:
        """Show "typing…" in the chat."""
        try:
            await self._bot.send_chat_action(chat_id=int(chat_id), action=ChatAction.TYPING)
        except TelegramError as err:
            logger.debug("typing indicator failed for chat %s: %s", chat_id, err)


class Tap(NamedTuple):
    """What one approval button's data names."""

    call_id: str
    choice: str


def _parse_tap(data: str | None) -> Tap | None:
    """The tap a button's data encodes, or `None` when it is not one of ours."""
    if data is None or data.count(":") < 2:
        return None
    _, call_id, choice = data.split(":", 2)
    return Tap(call_id, choice) if choice in CHOICES else None
