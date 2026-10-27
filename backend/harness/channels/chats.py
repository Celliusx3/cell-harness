"""Which conversation a chat is on."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID, BotNotFound, BotService
from harness.channels.protocol import Channel
from harness.channels.repository import ChatRepository, ChatState
from harness.session.log import Session
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService


async def state_of(
    repository: ChatRepository, channel: Channel, chat_id: str, bots: BotService
) -> ChatState:
    """This chat's state, on the conversation it writes into; `""` when that is nowhere."""
    stored = await repository.load(channel.channel, chat_id)
    known = stored if stored is not None else ChatState(channel=channel.channel, chat_id=chat_id)
    named = channel.conversation_for(chat_id)
    return known.model_copy(update={"conversation_id": _written_into(stored, named, bots)})


def bot_written_to(stored: ChatState | None) -> str | None:
    """The bot a stored chat writes to: its code's, else Assistant once stored; else `None`."""
    if stored is None:
        return None
    if stored.linked_bot_id is not None:
        return stored.linked_bot_id
    return ASSISTANT_ID if stored.conversation_id else None


def _written_into(stored: ChatState | None, named: str, bots: BotService) -> str:
    """The platform's choice unless a code linked the chat; else its bot's chat while active."""
    linked_by_code = stored is not None and stored.linked_bot_id is not None
    if named and not linked_by_code:
        return named
    bot_id = bot_written_to(stored)
    return "" if bot_id is None else _chat_of_active(bots, bot_id)


def _chat_of_active(bots: BotService, bot_id: str) -> str:
    try:
        return bots.chat_of(bots.active_bot(bot_id).id)
    except BotNotFound:
        return ""


async def session_for(
    repository: ChatRepository, sessions: SessionService, state: ChatState
) -> Session:
    """The session this chat's next turn runs in, created under its id if never written."""
    try:
        session = await sessions.resume(state.conversation_id)
    except SessionNotFoundError:
        session = await sessions.create(state.conversation_id)
    if await repository.load(state.channel, state.chat_id) != state:
        await repository.save(state)
    return session
