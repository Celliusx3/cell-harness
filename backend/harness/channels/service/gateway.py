"""One gateway, every platform."""

from __future__ import annotations

import functools
import logging

from harness.channels.domain.protocol import (
    Channel,
    ChannelDisposer,
    DuplicateChannelError,
    InboundMessage,
    PushChannel,
    RunningChannel,
    UnknownChannelError,
)
from harness.channels.repository.chat_repository import ChatRepository, ChatState
from harness.channels.service.chat_tasks import ChatTasks
from harness.channels.service.chats import state_of
from harness.channels.service.replies import ReplySender
from harness.channels.service.turn_follower import TurnFollower
from harness.runs.service.run import Run, RunAlreadyActiveError
from harness.runs.service.run_service import RunService
from harness.runtime.compaction import CompactionRefusedError, check_can_compact
from harness.session.domain.log import Session
from harness.session.repository.session_repository import SessionNotFoundError
from harness.session.service.session_service import SessionService
from harness.skills import SkillService
from harness.tools import Approval, ApprovalMode, Failure, Ok

logger = logging.getLogger("harness.channels")


class ChannelGateway:
    """Every platform's traffic, in both directions."""

    def __init__(
        self,
        repository: ChatRepository,
        runs: RunService,
        sessions: SessionService,
        skills: SkillService,
        *,
        public_url: str,
    ) -> None:
        self._repository = repository
        self.runs: RunService = runs
        self.sessions: SessionService = sessions
        self.skills: SkillService = skills
        self._channels: dict[str, RunningChannel] = {}
        self._is_receiving = False
        self._tasks = ChatTasks()
        self._follower = TurnFollower(
            repository,
            runs,
            sessions,
            skills,
            self._channels,
            self._tasks,
            ReplySender(repository, public_url=public_url),
        )

    def register(self, channel: Channel) -> ChannelDisposer:
        """Add one platform, receiving now if the gateway has started; the disposer takes it off."""
        if channel.channel in self._channels:
            raise DuplicateChannelError(f"{channel.channel!r} is already registered")
        running = RunningChannel(channel)
        self._channels[channel.channel] = running
        mode = "push" if isinstance(channel, PushChannel) else "pull"
        logger.info("%s channel registered (%s)", channel.channel, mode)
        if self._is_receiving:
            running.start()
        return functools.partial(self._remove, running)

    async def _remove(self, running: RunningChannel) -> None:
        """Take `running` off the gateway and stop it; nothing once it has gone."""
        if self._channels.get(running.name) is not running:
            return
        del self._channels[running.name]
        await running.aclose()
        logger.info("%s channel removed", running.name)

    @property
    def channel_names(self) -> list[str]:
        """The registered platforms, for logs and tests."""
        return list(self._channels)

    async def start(self) -> None:
        """Begin receiving on every registered channel, and on each registered from now on."""
        self._is_receiving = True
        for supervised in self._channels.values():
            supervised.start()

    async def receive(self, message: InboundMessage) -> Run | None:
        """One inbound message, from any platform; nothing at all for a chat linked to no bot."""
        self._require_registered(message.channel)
        state = await self._state(message.channel, message.chat_id)
        if _is_unlinked(state):
            return None
        content = self.skills.expand(message.text)
        if self.runs.active_run(state.conversation_id) is not None:
            await self._follower.queue(state, message.text, message.files)
            return None

        return await self._follower.start_turn_or_queue(state, content, message.files)

    async def clear(self, channel: str, chat_id: str) -> None:
        """Clear this chat in place, as a run that stops its turn and wipes it under the same id."""
        state = await self._state(channel, chat_id)
        if _is_unlinked(state):
            return
        await self._repository.save(state.model_copy(update={"pending": (), "pending_files": ()}))
        in_flight = self.runs.active_run(state.conversation_id)
        try:
            session = (
                in_flight.session
                if in_flight is not None
                else await self.sessions.read(state.conversation_id)
            )
        except SessionNotFoundError:
            return
        clearing = self.runs.clear(session)
        async with clearing.condition:
            await clearing.condition.wait_for(lambda: clearing.is_settled)
        if clearing.error is not None:
            raise clearing.error

    async def stop(self, channel: str, chat_id: str) -> bool:
        """Cancel the turn in flight, discarding anything queued behind it."""
        state = await self._state(channel, chat_id)
        if _is_unlinked(state):
            return False
        await self._repository.save(state.model_copy(update={"pending": (), "pending_files": ()}))
        return await self.runs.stop(state.conversation_id)

    async def set_approval_mode(self, channel: str, chat_id: str, mode: ApprovalMode) -> None:
        """Switch this chat to `mode` from its next call; nothing for a chat linked to no bot."""
        state = await self._state(channel, chat_id)
        if _is_unlinked(state):
            return
        await self.runs.set_approval_mode(state.conversation_id, mode)

    async def approval_mode(self, channel: str, chat_id: str) -> ApprovalMode | None:
        """The mode this chat's calls run under; `None` for a chat linked to no bot."""
        state = await self._state(channel, chat_id)
        if _is_unlinked(state):
            return None
        return await self.runs.approval_mode(state.conversation_id)

    async def is_linked(self, channel: str, chat_id: str) -> bool:
        """Whether this chat writes into a conversation."""
        self._require_registered(channel)
        return not _is_unlinked(await self._state(channel, chat_id))

    async def wait_until_drained(self, channel: str, chat_id: str) -> None:
        """Wait while this chat is between turns — see `TurnFollower.wait_until_drained`."""
        await self._follower.wait_until_drained(channel, chat_id)

    async def aclose(self) -> None:
        """Stop receiving on every channel left, then stop delivering."""
        self._is_receiving = False
        for supervised in tuple(self._channels.values()):
            await supervised.aclose()
        await self._tasks.aclose()

    def _require_registered(self, channel: str) -> None:
        if channel not in self._channels:
            raise UnknownChannelError(f"no channel registered for {channel!r}")

    async def _state(self, channel: str, chat_id: str) -> ChatState:
        platform = self._channels[channel].channel
        return await state_of(self._repository, platform, chat_id, self.runs.bots)

    def compact(self, session: Session, followers: tuple[ChatState, ...]) -> Run:
        """Begin a manual compaction, followed by `followers` and no other chat."""
        check_can_compact(session)
        run = self.runs.compact(session)
        for state in followers:
            self._follower.follow_in_chat(state, run)
        return run

    async def compact_chat(self, channel: str, chat_id: str) -> Run | None:
        """`/compact` from a chat: the run, or `None` when nothing can be compacted now."""
        self._require_registered(channel)
        state = await self._state(channel, chat_id)
        if _is_unlinked(state) or self.runs.active_run(state.conversation_id) is not None:
            return None
        try:
            session = await self.sessions.resume(state.conversation_id)
        except SessionNotFoundError:
            return None
        try:
            return self.compact(session, (state,))
        except (RunAlreadyActiveError, CompactionRefusedError):
            return None

    async def follow(self, run: Run) -> None:
        """Have every chat linked to `run`'s conversation hear it, for a turn no chat started."""
        for state in await self._repository.chats_of(run.session.id):
            if state.channel in self._channels:
                self._follower.follow_in_chat(state, run)

    async def resume(self, session: Session, call_id: str, outcome: Ok | Failure | Approval) -> Run:
        """Begin the turn that carries an answer, followed by the chats that were asked it."""
        states = await self._repository.chats_of(session.id)
        run = self.runs.resume(session, call_id, outcome)
        for state in states:
            if call_id in state.asked and state.channel in self._channels:
                answered = tuple(asked for asked in state.asked if asked != call_id)
                await self._repository.save(state.model_copy(update={"asked": answered}))
                self._follower.follow_in_chat(state, run)
        return run


def _is_unlinked(state: ChatState) -> bool:
    """Whether `state` writes nowhere, and so is ignored with a line at debug."""
    if state.conversation_id:
        return False
    logger.debug("%s chat %s is linked to no bot; ignored", state.channel, state.chat_id)
    return True
