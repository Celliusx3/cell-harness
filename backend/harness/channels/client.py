"""An answer that arrives from a chat, matched to the call pending for it.

The browser posts its answer to a call id it read off the stream. A chat cannot:
Telegram sends a pin with no reference to what asked for it. So what a chat
knows — which chat, and which tool its message answers — is turned into what
the service needs: the conversation's session, loaded for writing. The checks
are the service's, the same ones the route goes through; what it accepts
opens the turn that carries it.
"""

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
        # The gateway, not the run store: a chat's resumed turn must be
        # *followed* — delivered and drained — like the turn that asked.
        self._gateway = gateway
        self._client_tools = client_tools

    async def answer(self, channel: Channel, chat_id: str, name: str, raw: object) -> bool:
        """Hand `raw` — the platform's rendering of an answer to the tool named
        `name` — to this chat's pending call, opening the turn that carries
        it. `False` when it was not taken; the caller decides what an
        unprompted answer means."""
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
