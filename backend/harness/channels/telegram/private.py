"""The Telegram chats that are heard: private ones, never a group's."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatType

logger = logging.getLogger("harness.channels.telegram")


def private_chat_id(update: Update) -> str | None:
    """The private chat `update` came from; `None` for a group, a supergroup or a channel."""
    chat = update.effective_chat
    if chat is None:
        return None
    if chat.type != ChatType.PRIVATE:
        logger.debug("telegram %s chat %s is not private; ignored", chat.type, chat.id)
        return None
    return str(chat.id)
