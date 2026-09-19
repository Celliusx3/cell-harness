"""What happens after a turn starts: someone sees it to its end, then drains."""

from __future__ import annotations

import asyncio
import logging

from harness.channels.chat_tasks import ChatKey, ChatTasks
from harness.channels.chats import session_for, state_of
from harness.channels.protocol import Pushing, RunningChannel
from harness.channels.replies import Replies
from harness.channels.repository import ChatRepository, ChatState
from harness.runs.store import Run, RunAlreadyActive, RunStore
from harness.session.service import SessionService
from harness.skills import SkillService, UnknownSkill

logger = logging.getLogger("harness.channels")

QUEUE_JOIN = "\n"


class Following:
    """Follows every turn to its end for every chat that maps to it."""

    def __init__(
        self,
        repository: ChatRepository,
        runs: RunStore,
        sessions: SessionService,
        skills: SkillService,
        channels: dict[str, RunningChannel],
        tasks: ChatTasks,
        replies: Replies,
    ) -> None:
        self._repository = repository
        self._runs = runs
        self._sessions = sessions
        self._skills = skills
        self._channels = channels
        self._replies = replies
        self._tasks = tasks

    async def _state(self, channel: str, chat_id: str) -> ChatState:
        return await state_of(self._repository, self._channels[channel].channel, chat_id)

    async def turn_for_chat(self, state: ChatState, text: str) -> Run | None:
        """Resolve this chat's conversation and begin a turn in it."""
        state, session = await session_for(
            self._repository, self._sessions, self._channels[state.channel].channel, state
        )
        try:
            return self.begin(state, self._runs.start(session, text))
        except RunAlreadyActive:
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, text)})
            )
            return None

    def begin(self, state: ChatState, run: Run) -> Run:
        key = ChatKey(state.channel, state.chat_id)
        self._tasks.start(key, self._follow(key, run))
        return run

    async def _follow(self, key: ChatKey, run: Run) -> None:
        """See this turn to its end, then start whatever queued behind it."""
        channel, chat_id = key
        transport = self._channels[channel].channel
        if isinstance(transport, Pushing):
            await self._replies.deliver(transport, channel, chat_id, run)
        else:
            async with run.condition:
                await run.condition.wait_for(lambda: run.settled)
        await self._drain(channel, chat_id)

    async def _drain(self, channel: str, chat_id: str) -> None:
        """Run whatever queued during the last turn, as one turn."""
        state = await self._state(channel, chat_id)
        if not state.pending:
            return
        text = QUEUE_JOIN.join(state.pending)
        cleared = state.model_copy(update={"pending": ()})
        await self._repository.save(cleared)
        try:
            content = self._skills.expand(text)
        except UnknownSkill as err:
            logger.warning("queued /%s no longer names a skill; sent as text", err.name)
            content = text
        await self.turn_for_chat(cleared, content)

    async def drained(self, channel: str, chat_id: str) -> None:
        """Wait while this chat is between turns."""
        task = self._tasks.get((channel, chat_id))
        if task is None:
            return
        state = await self._state(channel, chat_id)
        if state.conversation_id and self._runs.active(state.conversation_id) is not None:
            return
        await asyncio.wait({task})
