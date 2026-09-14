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

import asyncio
import logging

from harness.channels.chats import session_for, state_of
from harness.channels.protocol import Channel, InboundMessage, Pushing, RunningChannel
from harness.channels.replies import Replies
from harness.channels.repository import ChatRepository, ChatState
from harness.runs.store import Run, RunAlreadyActive, RunStore
from harness.session.log import Session
from harness.session.service import SessionService

logger = logging.getLogger("harness.channels")

# Queued messages are joined with a newline because that is how they were typed.
QUEUE_JOIN = "\n"

# Telegram chat `123` and Discord channel `123` are different conversations, so
# nothing is keyed on the chat id alone.
ChatKey = tuple[str, str]


class DuplicateChannelError(RuntimeError):
    """Two channels registered under one platform name."""


class UnknownChannelError(RuntimeError):
    """A message arrived from a platform with no registered transport.

    Loud rather than ignored: it means a channel was wired to receive but not to
    reply, and a bot that reads everything and answers nothing looks like a hang.
    """


class ChannelGateway:
    """Every platform's traffic, in both directions."""

    def __init__(
        self,
        repository: ChatRepository,
        runs: RunStore,
        sessions: SessionService,
        *,
        public_url: str,
    ) -> None:
        self._repository = repository
        self._runs = runs
        self._sessions = sessions
        self._replies = Replies(repository, public_url=public_url)
        # One per platform, for the life of the server. Holds the channel itself
        # — the same object we reply through and listen on, which is why there is
        # one registry and not two.
        self._channels: dict[str, RunningChannel] = {}
        # One per chat with a turn in flight, for the life of that turn. A strong
        # reference is mandatory, not bookkeeping: asyncio holds only weak
        # references to tasks, so an unreferenced follower can be collected
        # mid-send. `hermes-agent` keeps the same collections for the same
        # reason. Only `aclose()` reads it — `/stop` goes through the run.
        #
        # In memory, so single-process. Multi-pod needs shared storage and a
        # lease; `RunStore` is what breaks first, not this. DESIGN.md §7.
        self._following: dict[ChatKey, asyncio.Task[None]] = {}

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
        logger.info(
            "%s channel registered (%s)",
            channel.channel,
            "push" if isinstance(channel, Pushing) else "pull",
        )

    @property
    def channels(self) -> list[str]:
        """The registered platforms, for logs and tests."""
        return list(self._channels)

    async def start(self) -> None:
        """Begin receiving on every registered channel."""
        for supervised in self._channels.values():
            await supervised.start()

    async def receive(self, message: InboundMessage) -> Run | None:
        """One inbound message, from any platform.

        Returns the run it started, or `None` when the message was queued behind
        one already going. A caller that must tell its client which happened — the
        browser's `202` says `queued` — needs that answer, and returning it beats
        making the caller ask the store a question we just answered.

        A redelivery is answered again, not recognised: the cost is answering the
        same question twice, which `channels/__init__.py`'s "dedupe by
        consequence" rule says is not worth guarding.
        """
        if message.channel not in self._channels:
            raise UnknownChannelError(f"no channel registered for {message.channel!r}")

        state = await self._state(message.channel, message.chat_id)
        if state.conversation_id and self._runs.active(state.conversation_id) is not None:
            # Held, not refused, on every channel. A phone cannot grey out its
            # composer, and a browser that refuses makes the person retype — so
            # the alternative is always dropping something someone wrote.
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, message.text)})
            )
            return None

        return await self._turn_for_chat(state, message.text)

    async def start_turn(self, session: Session, text: str, *, channel: str) -> Run:
        """Begin a turn for a session the caller already holds.

        Exists for `POST /api/conversations`, which creates the session itself.
        Routing that through `receive()` cannot work: `create()` writes nothing
        until the first flush, so a brand-new conversation is *absent* from disk,
        and a channel whose `on_missing` is `raise` would 404 on the conversation
        it had just made.
        """
        if channel not in self._channels:
            raise UnknownChannelError(f"no channel registered for {channel!r}")
        state = ChatState(channel=channel, chat_id=session.id, conversation_id=session.id)
        await self._repository.save(state)
        return self._begin(state, session, text)

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

    async def aclose(self) -> None:
        """Stop receiving, then stop delivering.

        That order is why this lives here and not in the caller: stop delivering
        first and a channel still listening starts a turn nobody will answer.
        """
        for supervised in self._channels.values():
            await supervised.aclose()
        for task in list(self._following.values()):
            task.cancel()
        if self._following:
            await asyncio.gather(*self._following.values(), return_exceptions=True)
        self._following.clear()

    async def _state(self, channel: str, chat_id: str) -> ChatState:
        return await state_of(self._repository, self._channels[channel].channel, chat_id)

    async def _turn_for_chat(self, state: ChatState, text: str) -> Run | None:
        """Resolve this chat's conversation and begin a turn in it."""
        state, session = await session_for(
            self._repository, self._sessions, self._channels[state.channel].channel, state
        )
        try:
            return self._begin(state, session, text)
        except RunAlreadyActive:
            # Raced with another inbound message. Queue rather than drop.
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, text)})
            )
            return None

    def _begin(self, state: ChatState, session: Session, text: str) -> Run:
        """Start the run, and follow it to its end."""
        run = self._runs.start(session, text)
        self._spawn_follower(state, run)
        return run

    def _spawn_follower(self, state: ChatState, run: Run) -> None:
        key = (state.channel, state.chat_id)
        # Deliberately no "cancel the previous follower for this chat". Two cannot
        # overlap: a turn only starts when none is active, and the one path that
        # spawns while another is live is the drain — where the "previous" *is*
        # the calling task, so the guard only cancelled itself.
        task = asyncio.create_task(self._follow(key, run))
        self._following[key] = task
        # Or every chat that has ever had a turn leaves a completed task here
        # until the process stops. Guarded on identity because a newer follower
        # may already own the key.
        task.add_done_callback(lambda done: self._forget(key, done))

    def _forget(self, key: ChatKey, task: asyncio.Task[None]) -> None:
        if self._following.get(key) is task:
            del self._following[key]

    async def _follow(self, key: ChatKey, run: Run) -> None:
        """See this turn to its end, then start whatever queued behind it.

        **Every channel gets one of these, including the ones nothing is sent to.**
        Delivery is the part that varies; the drain is not. A queued message has to
        be answered when the turn it waited for finishes, and if only push channels
        were followed, a browser message typed mid-turn would sit in `pending`
        until something else happened to arrive — which for a one-off question is
        never.

        **A turn is followed only by the channel that started it**, which has a
        consequence worth stating because the opposite is easy to assume: answer a
        Telegram conversation from the browser and the reply lands in the log and
        on screen, but *not* on the phone. Both channels share the conversation,
        not the delivery. Fixing it means following a turn from every channel
        mapped to its conversation, each with its own `delivered_through` — real,
        but nobody has asked for it, and it is a phase of its own.
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
        await self._turn_for_chat(cleared, text)
