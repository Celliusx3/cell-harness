"""`RunService` — driving a turn on a task nobody's connection owns."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing

from harness.app_events import AppEventService, ChatLoggedAppEvent, TurnStartedAppEvent
from harness.bots import BotService, GroupService
from harness.files import ChatFile
from harness.runs.service.discussion import discussion_events
from harness.runs.service.run import Run, RunAlreadyActiveError, wait_until_settled
from harness.runtime.events import TurnEvent
from harness.runtime.service import MODE_WITHOUT_TOOLSET, Runtime
from harness.session.domain.log import Session
from harness.session.domain.models import (
    ApprovalModeChange,
    HeardMessage,
    ScheduleChange,
    ScheduleChangeEvent,
    SessionEvent,
    ToolCallEvent,
)
from harness.session.repository.session_repository import SessionNotFoundError
from harness.session.service.session_service import SessionService
from harness.tools import Approval, ApprovalMode, Failure, Ok

logger = logging.getLogger("harness.runs")


class RunService:
    """Starts and stops turns, and knows which conversations are busy."""

    def __init__(
        self,
        sessions: SessionService,
        runtime: Runtime,
        bots: BotService,
        groups: GroupService,
        *,
        app_events: AppEventService,
    ) -> None:
        self._sessions = sessions
        self._runtime = runtime
        self._bots = bots
        self._groups = groups
        self._app_events = app_events
        self._runs: dict[str, Run] = {}

    @property
    def bots(self) -> BotService:
        """Who answers in each chat — for a chat app finding whether its linked bot still does."""
        return self._bots

    @property
    def groups(self) -> GroupService:
        """Who is in each chat and speaks next — for a route or tool that must tell a group's."""
        return self._groups

    @property
    def app_events(self) -> AppEventService:
        """The app's publisher, for the route that streams it."""
        return self._app_events

    def active_run(self, conversation_id: str) -> Run | None:
        """The run in flight for this conversation, if any."""
        return self._runs.get(conversation_id)

    def chats_spoken_in(self, bot_id: str) -> tuple[str, ...]:
        """The conversations whose run is in a turn of `bot_id`'s right now."""
        return tuple(
            chat_id for chat_id, run in self._runs.items() if run.session.speaker_id() == bot_id
        )

    def session_of_call(self, call_id: str) -> Session | None:
        """The log of the run in flight that asked for call `call_id`; `None` when none did."""
        return next(
            (run.session for run in self._runs.values() if _has_call(run.session, call_id)), None
        )

    def start(self, session: Session, prompt: str, *, files: tuple[ChatFile, ...] = ()) -> Run:
        """Begin the discussion the person's message opens; `EmptyGroupError` if none can answer."""
        if session.id in self._runs:
            raise RunAlreadyActiveError(session.id)
        speaker = self._groups.first_speaker(session, prompt)
        return self._converse(
            session, self._runtime.run(prompt, session=session, bot_id=speaker.id, files=files)
        )

    def hear(self, session: Session, message: HeardMessage) -> Run:
        """Begin the turn in which a bot's own chat answers a bot's message or a schedule."""
        if session.id in self._runs:
            raise RunAlreadyActiveError(session.id)
        speaker = self._groups.first_speaker(session, message.text)
        return self._converse(
            session, self._runtime.hear(message, session=session, bot_id=speaker.id)
        )

    async def hear_when_free(self, chat_id: str, message: HeardMessage) -> Run:
        """The turn `message` opens in `chat_id` once free, the chat created if never written."""
        while True:
            running = self._runs.get(chat_id)
            if running is not None:
                await wait_until_settled(running)
                continue
            session = await self._resumed_or_new_session(chat_id)
            if chat_id not in self._runs:
                return self.hear(session, message)

    def resume(self, session: Session, call_id: str, outcome: Ok | Failure | Approval) -> Run:
        """Begin the turn that answers a client tool for the bot that asked, then the queue's."""
        if session.id in self._runs:
            raise RunAlreadyActiveError(session.id)
        bot = self._groups.calling_bot(session, call_id)
        return self._converse(
            session, self._runtime.resume(call_id, outcome, session=session, bot_id=bot.id)
        )

    def compact(self, session: Session) -> Run:
        """Begin a manual compaction as its own run — no model turn, just the compaction events."""
        if session.id in self._runs:
            raise RunAlreadyActiveError(session.id)
        run = self._register_run(session)
        compaction = self._runtime.compact(session=session)
        run._turn_task = turn_task = asyncio.create_task(self._drain_turn(run, compaction))
        run._settle_task = asyncio.create_task(self._settle_when_done(run, turn_task))
        return run

    def clear(self, session: Session) -> Run:
        """Begin wiping this chat as a run of its own, taking over from the turn in flight."""
        in_flight = self._runs.get(session.id)
        run = self._register_run(session)
        run._settle_task = asyncio.create_task(self._end_then_wipe(in_flight, run))
        return run

    async def set_approval_mode(self, conversation_id: str, mode: ApprovalMode) -> None:
        """Switch the chat to `mode` from its next call; the mode already on writes nothing."""
        session = await self._resumed_or_new_session(conversation_id)
        if self._runtime.approval_mode(session) == mode:
            return
        await self._append(session, ApprovalModeChange(mode=mode))

    async def tell_schedule_change(self, chat_id: str, change: ScheduleChange) -> None:
        """Log `change` for the chat's next step, starting no turn; none in a chat never written."""
        await self.log_without_turn(
            chat_id, lambda turn: ScheduleChangeEvent(turn=turn, change=change)
        )

    async def log_without_turn(
        self, chat_id: str, event_for_turn: Callable[[int], SessionEvent]
    ) -> bool:
        """Log `event_for_turn(last turn)` for the next step, in no turn; `False` if unwritten."""
        session = await self._running_or_stored(chat_id)
        if session is None:
            return False
        await self._append(session, event_for_turn(max(session.next_turn() - 1, 0)))
        if chat_id not in self._runs:
            self._app_events.publish(ChatLoggedAppEvent(chat_id=chat_id))
        return True

    async def log_when_free(
        self, chat_id: str, event_for_turn: Callable[[int], SessionEvent]
    ) -> bool:
        """`log_without_turn` once no turn runs in `chat_id`, never between a call and result."""
        while (running := self._runs.get(chat_id)) is not None:
            await wait_until_settled(running)
        return await self.log_without_turn(chat_id, event_for_turn)

    async def approval_mode(self, conversation_id: str) -> ApprovalMode:
        """The mode the chat's next call runs under."""
        tools = self._runtime.tools
        if tools is None:
            return MODE_WITHOUT_TOOLSET
        run = self._runs.get(conversation_id)
        try:
            session = run.session if run is not None else await self._sessions.read(conversation_id)
        except SessionNotFoundError:
            return tools.default_mode
        return self._runtime.approval_mode(session)

    async def _resumed_or_new_session(self, conversation_id: str) -> Session:
        """The running turn's log, else the stored one, created when the chat was never written."""
        run = self._runs.get(conversation_id)
        if run is not None:
            return run.session
        try:
            stored = await self._sessions.resume(conversation_id)
        except SessionNotFoundError:
            stored = await self._sessions.create(conversation_id)
        started = self._runs.get(conversation_id)
        return started.session if started is not None else stored

    async def _running_or_stored(self, conversation_id: str) -> Session | None:
        """The running turn's log, else the stored one; `None` when the chat was never written."""
        run = self._runs.get(conversation_id)
        if run is not None:
            return run.session
        try:
            stored = await self._sessions.resume(conversation_id)
        except SessionNotFoundError:
            return None
        started = self._runs.get(conversation_id)
        return started.session if started is not None else stored

    async def _append(self, session: Session, event: SessionEvent) -> None:
        """Add `event` to `session`, make it durable, and wake whoever watches its running turn."""
        session.append(event)
        await self._sessions.flush(session)
        run = self._runs.get(session.id)
        if run is not None:
            await self._wake(run)

    async def stop(self, conversation_id: str) -> bool:
        """End a turn early."""
        run = self._runs.get(conversation_id)
        if run is None or run._turn_task is None:
            return False
        await self._end(run)
        return True

    async def aclose(self) -> None:
        """Stop every run, for a server shutting down."""
        for conversation_id in list(self._runs):
            await self.stop(conversation_id)

    def _converse(self, session: Session, opening: AsyncIterator[TurnEvent]) -> Run:
        """Run `opening` and the discussion after it on a task this service owns."""
        run = self._register_run(session)
        discussion = discussion_events(self._runtime, self._groups, session, opening)
        run._turn_task = turn_task = asyncio.create_task(self._drain_turn(run, discussion))
        run._settle_task = asyncio.create_task(self._settle_when_done(run, turn_task))
        return run

    def _register_run(self, session: Session) -> Run:
        """Record a new run for `session`, and publish that its turn started."""
        run = Run(session, session.next_number())
        self._runs[session.id] = run
        self._app_events.publish(TurnStartedAppEvent(chat_id=session.id))
        return run

    async def _end(self, run: Run) -> None:
        """Cancel `run`'s turn, if it has begun, and wait for the run to settle."""
        if run._turn_task is not None:
            run._turn_task.cancel()
        if run._settle_task is not None:
            await asyncio.shield(run._settle_task)

    async def _end_then_wipe(self, in_flight: Run | None, clearing: Run) -> None:
        """Own the clear: the run in flight ended and settled, then the wipe run as its turn."""
        if in_flight is not None:
            await self._end(in_flight)
        clearing._turn_task = turn_task = asyncio.create_task(self._wipe(clearing))
        await self._settle_when_done(clearing, turn_task)

    async def _wipe(self, run: Run) -> None:
        """Write the wiped log over the stored one, and show it to whoever watches `run`."""
        run.session = await self._sessions.clear(run.session.id)
        await self._wake(run)

    async def _drain_turn(self, run: Run, turn: AsyncIterator[object]) -> None:
        """Drive the turn, waking subscribers as the log grows."""
        async with aclosing(turn) as events:
            async for _ in events:
                await self._wake(run)

    async def _settle_when_done(self, run: Run, turn_task: asyncio.Task[None]) -> None:
        """Own the turn's ending. This task is never cancelled — see `stop`."""
        try:
            await turn_task
        except asyncio.CancelledError:
            pass
        except Exception as err:
            run.error = err
            logger.exception("run for conversation %s raised", run.session.id)
        finally:
            await self._settle(run)

    async def _settle(self, run: Run) -> None:
        """Make the turn durable, then release everyone waiting on it."""
        with contextlib.suppress(Exception):
            await self._sessions.flush(run.session)
        async with run.condition:
            run.is_settled = True
            run.condition.notify_all()
        if self._runs.get(run.session.id) is run:
            del self._runs[run.session.id]

    async def _wake(self, run: Run) -> None:
        async with run.condition:
            run.condition.notify_all()


def _has_call(session: Session, call_id: str) -> bool:
    return any(
        isinstance(event, ToolCallEvent) and event.call.id == call_id for event in session.events()
    )
