"""One gateway, every platform."""

from __future__ import annotations

import logging

from harness.agent.compaction import CompactionRefused
from harness.channels.chat_tasks import ChatTasks
from harness.channels.chats import state_of
from harness.channels.following import Following
from harness.channels.protocol import (
    Channel,
    DuplicateChannelError,
    InboundMessage,
    Pushing,
    RunningChannel,
    UnknownChannelError,
)
from harness.channels.replies import Replies
from harness.channels.repository import ChatRepository, ChatState
from harness.runs.store import Run, RunAlreadyActive, RunStore
from harness.session.log import Session
from harness.session.service import SessionService
from harness.skills import SkillService
from harness.tools.definition import Failure, Ok

logger = logging.getLogger("harness.channels")


class ChannelGateway:
    """Every platform's traffic, in both directions."""

    def __init__(
        self,
        repository: ChatRepository,
        runs: RunStore,
        sessions: SessionService,
        skills: SkillService,
        *,
        public_url: str,
        client_tools: frozenset[str] = frozenset(),
    ) -> None:
        self._repository = repository
        self._runs = runs
        self._sessions = sessions
        self._skills = skills
        self._channels: dict[str, RunningChannel] = {}
        self._tasks = ChatTasks()
        self._following = Following(
            repository,
            runs,
            sessions,
            skills,
            self._channels,
            self._tasks,
            Replies(repository, public_url=public_url, client_tools=client_tools),
        )

    def register(self, channel: Channel) -> None:
        """Add one platform: how to reply on it, and its background task."""
        if channel.channel in self._channels:
            raise DuplicateChannelError(f"{channel.channel!r} is already registered")
        self._channels[channel.channel] = RunningChannel(channel)
        mode = "push" if isinstance(channel, Pushing) else "pull"
        logger.info("%s channel registered (%s)", channel.channel, mode)

    @property
    def channels(self) -> list[str]:
        """The registered platforms, for logs and tests."""
        return list(self._channels)

    @property
    def runs(self) -> RunStore:
        """Which conversations are busy — for a chat deciding whether an answer can open a turn."""
        return self._runs

    @property
    def skills(self) -> SkillService:
        """What `/name` may name."""
        return self._skills

    async def start(self) -> None:
        """Begin receiving on every registered channel."""
        for supervised in self._channels.values():
            await supervised.start()

    async def receive(self, message: InboundMessage) -> Run | None:
        """One inbound message, from any platform."""
        self._require(message.channel)
        content = self._skills.expand(message.text)

        state = await self._state(message.channel, message.chat_id)
        if state.conversation_id and self._runs.active(state.conversation_id) is not None:
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, message.text)})
            )
            return None

        return await self._following.turn_for_chat(state, content)

    async def start_turn(self, session: Session, text: str, *, channel: str) -> Run:
        """Begin a turn for a session the caller already holds."""
        self._require(channel)
        content = self._skills.expand(text)
        state = ChatState(channel=channel, chat_id=session.id, conversation_id=session.id)
        await self._repository.save(state)
        return self._following.begin(state, self._runs.start(session, content))

    async def reset(self, channel: str, chat_id: str) -> None:
        """Point this chat at a fresh conversation (`/new`)."""
        state = await self._state(channel, chat_id)
        await self._repository.save(
            state.model_copy(update={"conversation_id": "", "delivered_through": 0, "pending": ()})
        )

    async def stop(self, channel: str, chat_id: str) -> bool:
        """Cancel the turn in flight, discarding anything queued behind it."""
        state = await self._state(channel, chat_id)
        await self._repository.save(state.model_copy(update={"pending": ()}))
        if not state.conversation_id:
            return False
        return await self._runs.stop(state.conversation_id)

    async def drained(self, channel: str, chat_id: str) -> None:
        """Wait while this chat is between turns — see `Following.drained`."""
        await self._following.drained(channel, chat_id)

    async def aclose(self) -> None:
        """Stop receiving, then stop delivering."""
        for supervised in self._channels.values():
            await supervised.aclose()
        await self._tasks.aclose()

    def _require(self, channel: str) -> None:
        if channel not in self._channels:
            raise UnknownChannelError(f"no channel registered for {channel!r}")

    async def _state(self, channel: str, chat_id: str) -> ChatState:
        return await state_of(self._repository, self._channels[channel].channel, chat_id)

    async def compact(self, session: Session) -> Run:
        """Begin a manual compaction, followed by every chat mapped to the conversation."""
        compactor = self._runs.compaction
        if compactor is not None and (reason := compactor.refusal(session)) is not None:
            raise CompactionRefused(reason)
        states = await self._repository.chats_of(session.id)
        run = self._runs.compact(session)
        for state in states:
            if state.channel in self._channels:
                self._following.begin(state, run)
        return run

    async def compact_chat(self, channel: str, chat_id: str) -> Run | None:
        """`/compact` from a chat: the run, or `None` when nothing can be compacted now."""
        self._require(channel)
        state = await self._state(channel, chat_id)
        if not state.conversation_id or self._runs.active(state.conversation_id) is not None:
            return None
        session = await self._sessions.resume(state.conversation_id)
        try:
            return await self.compact(session)
        except (RunAlreadyActive, CompactionRefused):
            return None

    async def resume(self, session: Session, call_id: str, outcome: Ok | Failure) -> Run:
        """Begin the turn that carries an answer to a client tool."""
        states = await self._repository.chats_of(session.id)
        run = self._runs.resume(session, call_id, outcome)
        for state in states:
            if state.channel in self._channels:
                self._following.begin(state, run)
        return run
