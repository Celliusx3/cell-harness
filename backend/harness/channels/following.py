"""What happens after a turn starts: someone sees it to its end, then drains.

Split from `gateway.py` at the length cap, along the seam that was already
there. The gateway decides *whether* a message starts a turn; this module owns
what follows — delivery to the chat that can be sent to, waiting for the ones
that read the log themselves, and starting whatever queued behind it. Every
chat mapped to a conversation gets a follower, including the ones nothing is
sent to: delivery varies, the drain does not.
"""

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

# Queued messages are joined with a newline because that is how they were typed.
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
        # The gateway's registry, shared by reference: a channel registered
        # after construction is followed like the rest.
        self._channels = channels
        self._replies = replies
        # The gateway's, shared: it closes them, and tests read them there.
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
            # Raced with another inbound message. Queue rather than drop.
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, text)})
            )
            return None

    def begin(self, state: ChatState, run: Run) -> Run:
        key = (state.channel, state.chat_id)
        self._tasks.start(key, self._follow(key, run))
        return run

    async def _follow(self, key: ChatKey, run: Run) -> None:
        """See this turn to its end, then start whatever queued behind it.

        **Every channel gets one of these, including the ones nothing is sent
        to.** Delivery varies; the drain does not: a queued message must be
        answered when the turn it waited for finishes, whoever is listening. A
        turn is followed only by the channel that started it — see
        `channels/__init__.py`, "one conversation, one delivery".
        """
        channel, chat_id = key
        transport = self._channels[channel].channel
        if isinstance(transport, Pushing):
            await self._replies.deliver(transport, channel, chat_id, run)
        else:
            # Nothing to send — this channel's client is reading the log itself.
            # Just wait for the turn to be over so the queue can drain.
            async with run.condition:
                await run.condition.wait_for(lambda: run.settled)
        await self._drain(channel, chat_id)

    async def _drain(self, channel: str, chat_id: str) -> None:
        """Run whatever queued during the last turn, as one turn.

        Three lines typed in five seconds are one thought; three replies to them
        is what makes a bot feel like a machine.
        """
        state = await self._state(channel, chat_id)
        if not state.pending:
            return
        text = QUEUE_JOIN.join(state.pending)
        cleared = state.model_copy(update={"pending": ()})
        await self._repository.save(cleared)
        try:
            content = self._skills.expand(text)
        except UnknownSkill as err:
            # Accepted while the skill existed, gone by the time its turn came.
            # Nobody is waiting on a reply to refuse into, so the literal line
            # goes to the model — the honest record of what was typed.
            logger.warning("queued /%s no longer names a skill; sent as text", err.name)
            content = text
        await self.turn_for_chat(cleared, content)

    async def drained(self, channel: str, chat_id: str) -> None:
        """Wait while this chat is between turns: one settled, and its follower
        is deciding whether a queued message starts the next. Returns at once
        when a turn is in flight or none is coming — a stream told `end` in
        that gap would otherwise park and miss the drained turn. The in-flight
        check matters: past the instant a drain starts a turn, waiting on the
        follower would mean waiting for the *whole next turn*.

        `asyncio.wait`, not `await task`: a waiter that is cancelled — a browser
        hanging up — must not cancel the follower, or closing a tab would lose
        the message it had queued. A watcher owns nothing.
        """
        task = self._tasks.get((channel, chat_id))
        if task is None:
            return
        state = await self._state(channel, chat_id)
        if state.conversation_id and self._runs.active(state.conversation_id) is not None:
            return
        await asyncio.wait({task})
