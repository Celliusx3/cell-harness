"""An answer that arrives from a chat, matched to the call pending for it."""

from __future__ import annotations

import logging

from harness.channels.chats import state_of
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import Channel
from harness.channels.repository import ChatRepository
from harness.runs.store import RunAlreadyActive
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from harness.tools.client import ClientToolService, Refused

logger = logging.getLogger("harness.channels")


class ChatAnswers:
    """Turns a chat's answer into the turn that carries it."""

    def __init__(
        self,
        repository: ChatRepository,
        sessions: SessionService,
        gateway: ChannelGateway,
        client_tools: ClientToolService,
    ) -> None:
        self._repository = repository
        self._sessions = sessions
        self._gateway = gateway
        self._client_tools = client_tools

    async def answer(self, channel: Channel, chat_id: str, name: str, raw: object) -> bool:
        """Hand a platform's answer to the tool `name` to this chat's pending call."""
        state = await state_of(self._repository, channel, chat_id)
        if (
            not state.conversation_id
            or self._gateway.runs.active(state.conversation_id) is not None
        ):
            return False
        try:
            session = await self._sessions.resume(state.conversation_id)
        except SessionNotFoundError:
            return False
        accepted = self._client_tools.accept_tool(session, name, raw)
        if isinstance(accepted, Refused):
            if accepted is Refused.DOES_NOT_FIT:
                logger.warning(
                    "%s chat %s answered %s with a body that does not fit",
                    channel.channel,
                    chat_id,
                    name,
                )
            return False
        try:
            await self._gateway.resume(session, accepted.call_id, accepted.outcome)
        except RunAlreadyActive:
            return False
        return True
