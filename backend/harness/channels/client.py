"""An answer that arrives from a chat, matched to the call pending for it."""

from __future__ import annotations

import logging
from collections.abc import Callable

from harness.channels.chats import state_of
from harness.channels.gateway import ChannelGateway
from harness.channels.protocol import Channel
from harness.channels.repository import ChatRepository
from harness.runs.service import RunAlreadyActive
from harness.session.log import Session
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from harness.tools.client import AcceptedAnswer, ClientToolService, RefusalReason

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

    @property
    def gated_tools(self) -> frozenset[str]:
        """The tools a chat asks with Allow and Deny buttons."""
        return self._client_tools.gated_tools

    async def answer(self, channel: Channel, chat_id: str, name: str, raw: object) -> bool:
        """Hand a platform's answer to the tool `name` to this chat's pending call."""
        return await self._resume_with(
            channel,
            chat_id,
            name,
            lambda session: self._client_tools.accept_by_tool_name(session, name, raw),
        )

    async def answer_call(self, channel: Channel, chat_id: str, call_id: str, raw: object) -> bool:
        """Hand a platform's decision on the call `call_id` to this chat's pending call."""
        return await self._resume_with(
            channel,
            chat_id,
            call_id,
            lambda session: self._client_tools.accept_by_call_id(session, call_id, raw),
        )

    async def _resume_with(
        self,
        channel: Channel,
        chat_id: str,
        answered: str,
        accept: Callable[[Session], AcceptedAnswer | RefusalReason],
    ) -> bool:
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
        verdict = accept(session)
        if isinstance(verdict, RefusalReason):
            if verdict is RefusalReason.DOES_NOT_FIT:
                logger.warning(
                    "%s chat %s answered %s with a body that does not fit",
                    channel.channel,
                    chat_id,
                    answered,
                )
            return False
        try:
            await self._gateway.resume(session, verdict.call_id, verdict.outcome)
        except RunAlreadyActive:
            return False
        return True
