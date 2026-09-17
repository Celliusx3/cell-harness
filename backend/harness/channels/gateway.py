"""One gateway, every platform.

Singular on purpose: the rules below do not vary by wire, so a brain per platform
is machinery without a reason. `hermes-agent` hands every adapter the same bound
handler; `duta-ilmu` does not model a channel as an object at all.

What it holds is the part that is the same everywhere — a message for a busy
conversation is queued rather than refused, the queue drains as *one* turn, and
outbound is driven by a cursor over the session log so a restart mid-send cannot
re-text a reply someone already has. The browser goes through here too, so those
rules are one implementation rather than two that drifted.

Two things vary, and both are read off the channel rather than branched on by
name: whether it can be **sent to** (`Pushing` — a browser cannot, it comes and
reads the log itself), and what a **missing conversation** means (`on_missing` — a
chat must recover, an API must 404).

It also supervises each channel's task, because the two halves of stopping belong
together: a channel must stop listening *before* delivery stops, or a message
arriving in the gap starts a turn nobody will answer.
"""

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
        # `/name` is expanded here and nowhere else, because this is the one
        # place every platform's text passes through — a phone and a browser
        # get the feature from the same line.
        self._skills = skills
        # One per platform, for the life of the server. Holds the channel itself
        # — the same object we reply through and listen on, which is why there is
        # one registry and not two.
        self._channels: dict[str, RunningChannel] = {}
        # One per chat with a turn in flight, for the life of that turn. Only
        # `drained()` and `aclose()` read it — `/stop` goes through the run.
        self._tasks = ChatTasks()
        # What happens after a turn starts — delivery, waiting, draining the
        # queue — lives in `following.py`; this class only decides what starts.
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
        """Add one platform: how to reply on it, and its background task.

        Not a constructor argument — a channel needs the gateway to hand messages
        to, so it cannot also be one.
        """
        if channel.channel in self._channels:
            # A dict would silently replace and a list would silently duplicate,
            # and duplicating means two pollers on one bot token — a 409 from
            # Telegram. Registering twice is a wiring mistake.
            raise DuplicateChannelError(f"{channel.channel!r} is already registered")
        self._channels[channel.channel] = RunningChannel(channel)
        # Logged because the alternative is a silent wrong answer: a channel that
        # typos `send_mesage` satisfies nothing, quietly becomes pull, and reads
        # every message while answering none. Naming the resolved mode at startup
        # is what makes that visible — the same fix phase 5 used for a poller that
        # died without saying so.
        mode = "push" if isinstance(channel, Pushing) else "pull"
        logger.info("%s channel registered (%s)", channel.channel, mode)

    @property
    def channels(self) -> list[str]:
        """The registered platforms, for logs and tests."""
        return list(self._channels)

    @property
    def runs(self) -> RunStore:
        """Which conversations are busy — for a chat deciding whether an
        answer can open a turn."""
        return self._runs

    @property
    def skills(self) -> SkillService:
        """What `/name` may name — for a channel composing the refusal when it
        named something else."""
        return self._skills

    async def start(self) -> None:
        """Begin receiving on every registered channel."""
        for supervised in self._channels.values():
            await supervised.start()

    async def receive(self, message: InboundMessage) -> Run | None:
        """One inbound message, from any platform.

        Returns the run it started, or `None` when the message was queued behind
        one already going — the browser's `202` says `queued` from this. A
        redelivery is answered again, not recognised: `channels/__init__.py`,
        "dedupe by consequence".
        """
        self._require(message.channel)
        # Before the busy check, so `/nonexistent` is refused now, while there is
        # a request to refuse it on — a queue has no one to tell.
        content = self._skills.expand(message.text)

        state = await self._state(message.channel, message.chat_id)
        if state.conversation_id and self._runs.active(state.conversation_id) is not None:
            # Held, not refused, on every channel. A phone cannot grey out its
            # composer, and a browser that refuses makes the person retype — so
            # the alternative is always dropping something someone wrote.
            # The typed text, not the expansion: the skill is read when the
            # turn starts, the same moment it would be for a message sent then.
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, message.text)})
            )
            return None

        return await self._following.turn_for_chat(state, content)

    async def start_turn(self, session: Session, text: str, *, channel: str) -> Run:
        """Begin a turn for a session the caller already holds.

        Exists for `POST /api/conversations`, which creates the session itself.
        Routing that through `receive()` cannot work: `create()` writes nothing
        until the first flush, so a brand-new conversation is *absent* from disk,
        and a channel whose `on_missing` is `raise` would 404 on the conversation
        it had just made.
        """
        self._require(channel)
        content = self._skills.expand(text)
        state = ChatState(channel=channel, chat_id=session.id, conversation_id=session.id)
        await self._repository.save(state)
        return self._following.begin(state, self._runs.start(session, content))

    async def reset(self, channel: str, chat_id: str) -> None:
        """Point this chat at a fresh conversation (`/new`).

        Cleared rather than replaced, so `/new` three times leaves three empty
        sessions nowhere. The old one stays on disk and in the browser's list.
        """
        state = await self._state(channel, chat_id)
        await self._repository.save(
            state.model_copy(update={"conversation_id": "", "delivered_through": 0, "pending": ()})
        )

    async def stop(self, channel: str, chat_id: str) -> bool:
        """Cancel the turn in flight, discarding anything queued behind it.

        Clearing `pending` is the point — answering the queue afterwards is the
        opposite of what was asked.
        """
        state = await self._state(channel, chat_id)
        await self._repository.save(state.model_copy(update={"pending": ()}))
        if not state.conversation_id:
            return False
        return await self._runs.stop(state.conversation_id)

    async def drained(self, channel: str, chat_id: str) -> None:
        """Wait while this chat is between turns — see `Following.drained`."""
        await self._following.drained(channel, chat_id)

    async def aclose(self) -> None:
        """Stop receiving, then stop delivering.

        That order is why this lives here and not in the caller: stop delivering
        first and a channel still listening starts a turn nobody will answer.
        """
        for supervised in self._channels.values():
            await supervised.aclose()
        await self._tasks.aclose()

    def _require(self, channel: str) -> None:
        if channel not in self._channels:
            raise UnknownChannelError(f"no channel registered for {channel!r}")

    async def _state(self, channel: str, chat_id: str) -> ChatState:
        return await state_of(self._repository, self._channels[channel].channel, chat_id)

    async def compact(self, session: Session) -> Run:
        """Begin a manual compaction, followed by every chat mapped to the
        conversation — like `resume`, nothing started it, so nothing else
        would. The browser follows it through the stream; a phone is told the
        one line `replies.py` sends on the end."""
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
        """`/compact` from a chat: compact this chat's conversation, or `None`
        when it has none or a turn is running — the command composes what to
        say from that."""
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
        """Begin the turn that carries an answer to a client tool.

        No chat in hand, on purpose: the answer may come from a Telegram pin
        or from the browser page a Discord link opened, and either way the
        turn is followed — delivered, then drained — by *every* chat mapped to
        the conversation; nothing started it, so nothing else would. Chats are
        looked up first: a lookup that fails must leave nothing running unfollowed.
        """
        states = await self._repository.chats_of(session.id)
        run = self._runs.resume(session, call_id, outcome)
        for state in states:
            if state.channel in self._channels:
                self._following.begin(state, run)
        return run
