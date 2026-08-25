"""One gateway, every platform.

Singular on purpose: the rules below do not vary by wire, so a brain per platform
is machinery without a reason. `hermes-agent` hands every adapter the same bound
handler; `duta-ilmu` does not model a channel as an object at all.

What it holds is the part that is the same everywhere — a message for a busy
conversation is queued rather than refused, the queue drains as *one* turn, and
outbound is driven by a cursor over the session log so a restart mid-send cannot
re-text a reply someone already has. The only per-platform thing it touches is
which transport to reply through.

It also supervises each channel's task, because the two halves of stopping belong
together: a channel must stop listening *before* delivery stops, or a message
arriving in the gap starts a turn nobody will answer.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from harness.channels.repository import ChatRepository, ChatState
from harness.channels.transport import Channel, InboundMessage
from harness.runs.store import Run, RunAlreadyActive, RunStore
from harness.runs.subscribe import subscribe
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
        # One per chat being replied to, for the life of one turn. A strong
        # reference is mandatory, not bookkeeping: asyncio holds only weak
        # references to tasks, so an unreferenced delivery can be collected
        # mid-send. `hermes-agent` keeps the same collections for the same
        # reason. Only `aclose()` reads it — `/stop` goes through the run.
        #
        # In memory, so single-process. Multi-pod needs shared storage and a
        # lease; `RunStore` is what breaks first, not this. DESIGN.md §7.
        self._deliveries: dict[ChatKey, asyncio.Task[None]] = {}

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

    @property
    def channels(self) -> list[str]:
        """The registered platforms, for logs and tests."""
        return list(self._channels)

    async def start(self) -> None:
        """Begin receiving on every registered channel."""
        for supervised in self._channels.values():
            await supervised.start()

    async def receive(self, message: InboundMessage) -> None:
        """One inbound message, from any platform.

        A redelivery is answered again, not recognised: the cost is answering the
        same question twice, which `channels/__init__.py`'s "dedupe by
        consequence" rule says is not worth guarding.
        """
        if message.channel not in self._channels:
            raise UnknownChannelError(f"no channel registered for {message.channel!r}")

        state = await self._state(message.channel, message.chat_id)
        if state.conversation_id and self._runs.active(state.conversation_id) is not None:
            # Held, not refused: a phone cannot grey out its composer, so the
            # alternative is dropping something someone typed.
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, message.text)})
            )
            return

        await self._start_turn(state, message.text)

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
        for task in list(self._deliveries.values()):
            task.cancel()
        if self._deliveries:
            await asyncio.gather(*self._deliveries.values(), return_exceptions=True)
        self._deliveries.clear()

    async def _state(self, channel: str, chat_id: str) -> ChatState:
        """This chat's state, defaulted for one we have not seen.

        Not persisted here, so a chat that only ever sent `/stop` leaves nothing
        behind. Whoever changes something saves it.
        """
        stored = await self._repository.load(channel, chat_id)
        return stored or ChatState(channel=channel, chat_id=chat_id)

    async def _start_turn(self, state: ChatState, text: str) -> None:
        """Begin a turn and start delivering its output."""
        if state.conversation_id:
            try:
                session = await self._sessions.resume(state.conversation_id)
            except SessionNotFoundError:
                # Reachable: `/stop` a first message before the loop's first
                # checkpoint and the run is cancelled having appended nothing, so
                # lazy materialization leaves no file while the chat already
                # points at the id. Without this the chat is *permanently*
                # broken — every later message resumes an id that will never
                # exist. Dropping it costs nothing; the conversation is empty.
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

        try:
            run = self._runs.start(session, text)
        except RunAlreadyActive:
            # Raced with another inbound message. Queue rather than drop.
            await self._repository.save(
                state.model_copy(update={"pending": (*state.pending, text)})
            )
            return

        self._spawn_delivery(state, run)

    def _spawn_delivery(self, state: ChatState, run: Run) -> None:
        key = (state.channel, state.chat_id)
        # Deliberately no "cancel the previous delivery for this chat". Two
        # cannot overlap: a turn only starts when none is active, and the one
        # path that spawns while another is live is the drain — where the
        # "previous" *is* the calling task, so the guard only cancelled itself.
        task = asyncio.create_task(self._deliver(key, run))
        self._deliveries[key] = task
        # Or every chat that has ever had a reply leaves a completed task here
        # until the process stops. Guarded on identity because a newer delivery
        # may already own the key.
        task.add_done_callback(lambda done: self._forget(key, done))

    def _forget(self, key: ChatKey, task: asyncio.Task[None]) -> None:
        if self._deliveries.get(key) is task:
            del self._deliveries[key]

    async def _deliver(self, key: ChatKey, run: Run) -> None:
        """Send this turn's replies, then start whatever queued behind it."""
        channel, chat_id = key
        transport = self._channels[channel].channel
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
        await self._start_turn(cleared, text)

    async def _keep_typing(self, transport: Channel, chat_id: str) -> None:
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
        else:
            logger.warning("%s channel stopped; it will not answer", self.name)
