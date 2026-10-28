"""Six-digit codes from a bot's page, kept in memory, that link a direct chat to that bot."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from typing import NamedTuple

from harness.bots import ASSISTANT_ID, Bot, BotNotFound, BotService
from harness.channels.chats import bot_written_to
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import InboundMessage
from harness.channels.repository import ChatRepository, ChatState
from harness.secrets.models.details import ChatPlatform

logger = logging.getLogger("harness.channels")

LINK_CODE_SECONDS = 15 * 60
CODE_DIGITS = 6
WRONG_GUESSES_BEFORE_SILENCE = 5

Clock = Callable[[], float]


class LinkCode(NamedTuple):
    """One live code: the bot it links to, the platform it works on, and when it stops working."""

    code: str
    bot_id: str
    platform: ChatPlatform
    expires_at: float


class GuessingChat(NamedTuple):
    platform: str
    chat_id: str


class LinkCodes:
    """The live codes, each used once, and the chats silenced for guessing wrong."""

    def __init__(self, now: Clock) -> None:
        self._now = now
        self._live: dict[str, LinkCode] = {}
        self._wrong_guesses: dict[GuessingChat, int] = {}
        self._silenced_until: dict[GuessingChat, float] = {}

    def issue(self, bot_id: str, platform: ChatPlatform) -> LinkCode:
        """A fresh code linking a `platform` chat to `bot_id`, voiding the one issued before it."""
        self._prune()
        kept = {
            code: live
            for code, live in self._live.items()
            if (live.bot_id, live.platform) != (bot_id, platform)
        }
        issued = LinkCode(_unused_code(kept), bot_id, platform, self._now() + LINK_CODE_SECONDS)
        self._live = {**kept, issued.code: issued}
        return issued

    def redeem(self, platform: str, chat_id: str, text: str) -> str | None:
        """The bot a live code for `platform` names, when `text` is exactly that code; used up."""
        guess = text.strip()
        if not _is_a_code(guess):
            return None
        self._prune()
        chat = GuessingChat(platform, chat_id)
        if chat in self._silenced_until:
            return None
        live = self._live.get(guess)
        if live is None or live.platform != platform:
            self._count_wrong_guess(chat)
            return None
        self._live = {code: kept for code, kept in self._live.items() if code != guess}
        return live.bot_id

    def _count_wrong_guess(self, chat: GuessingChat) -> None:
        wrong = self._wrong_guesses.get(chat, 0) + 1
        if wrong < WRONG_GUESSES_BEFORE_SILENCE:
            self._wrong_guesses = {**self._wrong_guesses, chat: wrong}
            return
        logger.debug("%s chat %s guessed %d wrong codes and is silenced", *chat, wrong)
        self._wrong_guesses = {key: n for key, n in self._wrong_guesses.items() if key != chat}
        self._silenced_until = {**self._silenced_until, chat: self._now() + LINK_CODE_SECONDS}

    def _prune(self) -> None:
        """Forget every code that has expired, and every silence that has ended."""
        now = self._now()
        self._live = {code: live for code, live in self._live.items() if live.expires_at > now}
        self._silenced_until = {
            chat: until for chat, until in self._silenced_until.items() if until > now
        }


def _is_a_code(text: str) -> bool:
    return len(text) == CODE_DIGITS and text.isascii() and text.isdigit()


def _unused_code(live: dict[str, LinkCode]) -> str:
    """Six random digits that are no live code."""
    while True:
        code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
        if code not in live:
            return code


class ChatLinks:
    """Each Telegram or Discord chat's link to the bot whose chat it writes into."""

    def __init__(self, chats: ChatRepository, codes: LinkCodes, bots: BotService) -> None:
        self._chats = chats
        self._codes = codes
        self._bots = bots

    async def link_if_code(self, platform: str, chat_id: str, text: str) -> Bot | None:
        """The active bot `text`'s code names, this chat now writing into its chat; else `None`."""
        bot_id = self._codes.redeem(platform, chat_id, text)
        if bot_id is None:
            return None
        try:
            bot = self._bots.active_bot(bot_id)
        except BotNotFound:
            logger.info(
                "%s chat %s sent a code for %s, which is not active", platform, chat_id, bot_id
            )
            return None
        stored = await self._chats.load(platform, chat_id)
        state = stored or ChatState(channel=platform, chat_id=chat_id)
        await self._chats.save(_moved_dropping_old_queue(state, bot.id, self._bots.chat_of(bot.id)))
        logger.info("%s chat %s linked to bot %s", platform, chat_id, bot.id)
        return bot

    async def store_on_assistant_unless_stored(self, platform: str, chat_id: str) -> None:
        """Store this chat writing into Assistant's chat, unless it is stored already."""
        if await self._chats.load(platform, chat_id) is not None:
            return
        assistants = self._bots.chat_of(ASSISTANT_ID)
        await self._chats.save(
            ChatState(channel=platform, chat_id=chat_id, conversation_id=assistants)
        )


async def link_or_receive(
    links: ChatLinks, gateway: ChannelGateway, message: InboundMessage
) -> str | None:
    """The reply naming the bot a code links this chat to; else `None`, once the gateway has it."""
    bot = await links.link_if_code(message.channel, message.chat_id, message.text)
    if bot is not None:
        return f"Linked to {bot.name}. Say hi."
    await gateway.receive(message)
    return None


def _moved_dropping_old_queue(state: ChatState, bot_id: str, conversation_id: str) -> ChatState:
    linked = state.model_copy(update={"linked_bot_id": bot_id, "conversation_id": conversation_id})
    if bot_written_to(state) == bot_id:
        return linked
    return linked.model_copy(update={"pending": (), "pending_files": ()})
