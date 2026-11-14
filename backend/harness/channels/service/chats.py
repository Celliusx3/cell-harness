"""Which conversation a chat is on."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID, BotNotFound, BotService
from harness.channels.domain.protocol import Channel
from harness.channels.repository.chat_repository import ChatRepository, ChatState
from harness.session.domain.log import Session
from harness.session.repository.session_repository import SessionNotFoundError
from harness.session.service.session_service import SessionService


async def state_of(
    repository: ChatRepository, channel: Channel, chat_id: str, bots: BotService
) -> ChatState:
    """This chat's state, on the conversation it writes into; `""` when that is nowhere."""
    stored = await repository.load(channel.channel, chat_id)
    known = stored if stored is not None else ChatState(channel=channel.channel, chat_id=chat_id)
    platform_conversation_id = channel.conversation_id_for(chat_id)
    return known.model_copy(
        update={
            "conversation_id": _conversation_id_written_into(stored, platform_conversation_id, bots)
        }
    )


def bot_id_written_to(stored: ChatState | None) -> str | None:
    """The bot a stored chat writes to: its code's, else Assistant once stored; else `None`."""
    if stored is None:
        return None
    if stored.linked_bot_id is not None:
        return stored.linked_bot_id
    return ASSISTANT_ID if stored.conversation_id else None


def _conversation_id_written_into(
    stored: ChatState | None, platform_conversation_id: str, bots: BotService
) -> str:
    """The platform's choice unless a code linked the chat; else its bot's chat while active."""
    linked_by_code = stored is not None and stored.linked_bot_id is not None
    if platform_conversation_id and not linked_by_code:
        return platform_conversation_id
    bot_id = bot_id_written_to(stored)
    return "" if bot_id is None else _active_bot_conversation_id(bots, bot_id)


def _active_bot_conversation_id(bots: BotService, bot_id: str) -> str:
    try:
        return bots.chat_of(bots.active_bot(bot_id).id)
    except BotNotFound:
        return ""


async def open_chat_session(
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
