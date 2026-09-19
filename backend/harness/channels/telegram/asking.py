"""How a client tool's ask is put to a Telegram chat."""

from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup

from harness.channels.protocol import Pushing
from harness.tools.client import PendingCall
from harness.tools.native.location import LOCATION

ASK = {LOCATION: "The assistant needs your location to answer. Share it?"}
SHARE_LABEL = "Share my location"
ASK_BY_LINK = "The assistant needs something from your device. Open the page to answer."
NO_ANSWER_PAGE = "(Answering from Telegram needs `web.public_url` to be set.)"


async def ask_client(channel: Pushing, bot, chat_id: str, request: PendingCall, url: str) -> None:
    """Put `request` to the chat: the location keyboard, or the page."""
    if request.name != LOCATION:
        if not url:
            await channel.send_message(chat_id, f"{ASK_BY_LINK} {NO_ANSWER_PAGE}")
            return
        await channel.send_link(chat_id, ASK_BY_LINK, url)
        return
    button = KeyboardButton(SHARE_LABEL, request_location=True)
    await bot.send_message(
        chat_id=int(chat_id),
        text=ASK[LOCATION],
        reply_markup=ReplyKeyboardMarkup([[button]], one_time_keyboard=True, resize_keyboard=True),
    )
