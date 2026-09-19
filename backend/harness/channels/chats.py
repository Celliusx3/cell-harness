"""Which conversation a chat is on."""

from __future__ import annotations

import logging

from harness.channels.protocol import Channel
from harness.channels.repository import ChatRepository, ChatState
from harness.session.log import Session
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService

logger = logging.getLogger("harness.channels")


async def state_of(repository: ChatRepository, channel: Channel, chat_id: str) -> ChatState:
    """This chat's state, defaulted for one we have not seen."""
    stored = await repository.load(channel.channel, chat_id)
    if stored is not None:
        return stored
    if channel.on_missing == "raise":
        return ChatState(channel=channel.channel, chat_id=chat_id, conversation_id=chat_id)
    return ChatState(channel=channel.channel, chat_id=chat_id)


async def session_for(
    repository: ChatRepository, sessions: SessionService, channel: Channel, state: ChatState
) -> tuple[ChatState, Session]:
    """The session this chat's next turn runs in, and the state that names it."""
    if state.conversation_id:
        try:
            session = await sessions.resume(state.conversation_id)
        except SessionNotFoundError:
            if channel.on_missing == "raise":
                raise
            logger.info(
                "%s chat %s pointed at unwritten conversation %s; starting fresh",
                state.channel,
                state.chat_id,
                state.conversation_id,
            )
            session = await sessions.create()
            state = state.model_copy(update={"conversation_id": session.id, "delivered_through": 0})
            await repository.save(state)
    else:
        session = await sessions.create()
        state = state.model_copy(update={"conversation_id": session.id})
        await repository.save(state)

    if not await repository.load(state.channel, state.chat_id):
        await repository.save(state)
    return state, session
