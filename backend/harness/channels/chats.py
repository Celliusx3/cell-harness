"""Which conversation a chat is on."""

from __future__ import annotations

from harness.channels.protocol import Channel
from harness.channels.repository import ChatRepository, ChatState
from harness.session.log import Session
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService


async def state_of(repository: ChatRepository, channel: Channel, chat_id: str) -> ChatState:
    """This chat's state, on the conversation its platform says it writes into."""
    stored = await repository.load(channel.channel, chat_id)
    known = stored if stored is not None else ChatState(channel=channel.channel, chat_id=chat_id)
    return known.model_copy(update={"conversation_id": channel.conversation_for(chat_id)})


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
