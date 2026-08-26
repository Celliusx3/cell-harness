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
import contextlib
import logging

from harness.channels.repository import ChatRepository, ChatState
from harness.channels.transport import Channel, InboundMessage, Pushing
from harness.runs.store import Run, RunAlreadyActive, RunStore
from harness.runs.subscribe import subscribe
from harness.session.log import Session
from harness.session.models import AssistantMessageEvent
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService

logger = logging.getLogger("harness.channels")

# Telegram clears its typing indicator after ~5s and Discord after ~10, so this
# is a heartbeat rather than a state with an off switch.
TYPING_INTERVAL_SECONDS = 4.0

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
    ) -> None:
        self._repository = repository
        self._runs = runs
        self._sessions = sessions
        # One per platform, for the life of the server. Holds the channel itself
        # — the same object we reply through and listen on, which is why there is
        # one registry and not two.
        self._channels: dict[str, _RunningChannel] = {}
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
        self._channels[channel.channel] = _RunningChannel(channel)
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
        """This chat's state, defaulted for one we have not seen.

        Not persisted here, so a chat that only ever sent `/stop` leaves nothing
        behind. Whoever changes something saves it.
        """
        stored = await self._repository.load(channel, chat_id)
        if stored is not None:
            return stored
        if self._channels[channel].channel.on_missing == "raise":
            # **A client channel's chat id *is* a conversation id.** It has no
            # stored mapping for a conversation it has not written to before, and
            # it must not invent one — so the id it was given is the answer, and
            # `resume` decides later whether it names anything.
            #
            # This is what lets the browser reply to a conversation that started
            # on Telegram: there is no `("web", c0)` mapping, but `c0` is a real
            # conversation and that is all a browser needs to know.
            #
            # Resolved *here* rather than at the point of use, so `receive`'s busy
            # check sees the conversation id too. It did not, briefly, and the
            # consequence was severe: the check fell through, `resume` ran against
            # a turn already executing, and crash repair committed a synthetic
            # result for a tool call still in flight.
            return ChatState(channel=channel, chat_id=chat_id, conversation_id=chat_id)
        return ChatState(channel=channel, chat_id=chat_id)

    async def _turn_for_chat(self, state: ChatState, text: str) -> Run | None:
        """Resolve this chat's conversation and begin a turn in it."""
        on_missing = self._channels[state.channel].channel.on_missing
        if state.conversation_id:
            try:
                session = await self._sessions.resume(state.conversation_id)
            except SessionNotFoundError:
                if on_missing == "raise":
                    # A client that named an id is asking about *that* id, so the
                    # honest answer is that it does not exist. Recreating here
                    # would turn a mistyped URL into a new conversation.
                    raise
                # Reachable: `/stop` a first message before the loop's first
                # checkpoint and the run is cancelled having appended nothing, so
                # lazy materialization leaves no file while the chat already
                # points at the id. Without this a *chat* is permanently broken —
                # every later message resumes an id that will never exist, and the
                # person holding the phone has no way to fix it. Dropping it costs
                # nothing; the conversation is empty by definition.
                logger.info(
                    "%s chat %s pointed at unwritten conversation %s; starting fresh",
                    state.channel,
                    state.chat_id,
                    state.conversation_id,
                )
                session = await self._sessions.create()
                state = state.model_copy(
                    update={"conversation_id": session.id, "delivered_through": 0}
                )
                await self._repository.save(state)
        else:
            # First message here, or the first after `/new`. Created now rather
            # than at first contact so the id always names a conversation that
            # will actually exist.
            session = await self._sessions.create()
            state = state.model_copy(update={"conversation_id": session.id})
            await self._repository.save(state)

        if not await self._repository.load(state.channel, state.chat_id):
            # First time we have seen this chat, including a client channel that
            # resolved its conversation by id above. Stored now so a message
            # arriving mid-turn has a `pending` to go into.
            await self._repository.save(state)

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
            await self._deliver(transport, key, run)
        else:
            # Nothing to send — this channel's client is reading the log itself.
            # Just wait for the turn to be over so the queue can drain.
            async with run.condition:
                await run.condition.wait_for(lambda: run.settled)
        await self._drain(channel, chat_id)

    async def _deliver(self, transport: Pushing, key: ChatKey, run: Run) -> None:
        """Send this turn's replies as they land."""
        channel, chat_id = key
        typing = asyncio.create_task(self._keep_typing(transport, chat_id))
        try:
            state = await self._state(channel, chat_id)
            cursor = state.delivered_through
            async for event in subscribe(run, after=cursor):
                cursor += 1
                if not isinstance(event, AssistantMessageEvent):
                    continue
                # A tool-calling step records an assistant message with empty
                # content — the model asked for a tool and said nothing. Sending
                # an empty message is an error.
                if not event.message.content.strip():
                    continue
                await transport.send_message(chat_id, event.message.content)
                # Advanced only after the send returns. A crash before this
                # re-sends one message, a crash after sends none — and of the
                # two, a duplicate is the recoverable one.
                state = await self._state(channel, chat_id)
                await self._repository.save(state.model_copy(update={"delivered_through": cursor}))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("delivery failed for %s chat %s", channel, chat_id)
        finally:
            typing.cancel()
            with contextlib.suppress(BaseException):
                await typing

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

    async def _keep_typing(self, transport: Pushing, chat_id: str) -> None:
        """Refresh the typing indicator until cancelled."""
        while True:
            await transport.send_typing(chat_id)
            await asyncio.sleep(TYPING_INTERVAL_SECONDS)


class _RunningChannel:
    """A channel, and the task listening on it — useless apart, and looked up
    by the same platform name."""

    def __init__(self, channel: Channel) -> None:
        # Public, because the gateway replies through the same object it
        # supervises.
        self.channel = channel
        self._task: asyncio.Task[None] | None = None

    @property
    def name(self) -> str:
        return self.channel.channel

    async def start(self) -> None:
        logger.info("%s channel starting", self.name)
        self._task = asyncio.create_task(self.channel.run())
        # Without this a dead channel is *silent*: `create_task` holds the
        # exception until someone awaits the task, and nothing does until
        # shutdown. That is how a dead poller once looked like a working one.
        self._task.add_done_callback(self._report_exit)

    async def aclose(self) -> None:
        """Stop receiving. Delivery is shared, so the gateway closes that once
        after every channel is down — here would close it on the first."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def _report_exit(self, task: asyncio.Task[None]) -> None:
        """Say something when receiving ends on its own."""
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("%s channel stopped: %s", self.name, error, exc_info=error)
        elif isinstance(self.channel, Pushing):
            logger.warning("%s channel stopped; it will not answer", self.name)
        else:
            # A pull channel's `run()` returning means only that it stopped
            # waiting — its receiving is somewhere else entirely (uvicorn serves
            # `WebChannel`'s routes), so it goes on answering. Saying "it will not
            # answer" here would be the false alarm that teaches people to ignore
            # the true one.
            logger.info("%s channel stopped waiting", self.name)
