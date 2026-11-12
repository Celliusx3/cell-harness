"""`Runtime` — gather context, act, repeat until nothing is owed."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import aclosing
from dataclasses import dataclass

from harness.files import ChatFile, ChatFileService
from harness.images import ImageService
from harness.llm import Message, SystemMessage, ToolCall, ToolMessage, UserMessage
from harness.prompts import (
    APPROVAL_MODE_ASK,
    APPROVAL_MODE_AUTO,
    SKIPPED_RESULT,
    SYSTEM_REMINDER,
)
from harness.runtime.compaction import (
    CompactionEvent,
    CompactionRefused,
    check_can_compact,
    run_compaction,
)
from harness.runtime.events import AgentPending, TurnEvent
from harness.runtime.hooks import HookChain
from harness.runtime.models import BotModels, ModelChoice
from harness.runtime.system_prompt import system_text
from harness.runtime.tool_run import run_approved_call, settled_result
from harness.runtime.turn import run_turn
from harness.session.derive import derive_messages, without_images
from harness.session.log import ApprovalModeSwitch, Session
from harness.session.models import (
    ApprovalGrant,
    ApprovalModeChanged,
    BotMessage,
    BotMessageEvent,
    HeardMessage,
    ScheduleReminderEvent,
    ServerInstructionsEvent,
    TicketReport,
    TicketReportEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repair import unanswered
from harness.tools import Approval, ApprovalMode, Failure, Ok, Toolset

SKIPPED = "SKIPPED"
MODE_WITHOUT_TOOLSET: ApprovalMode = "auto"
APPROVAL_MODE_SENTENCES: Mapping[ApprovalMode, str] = {
    "ask": APPROVAL_MODE_ASK,
    "auto": APPROVAL_MODE_AUTO,
}


@dataclass(frozen=True)
class Runtime:
    """A runtime that answers by running the tool loop."""

    models: BotModels
    images: ImageService
    """The images a model that sees is shown."""
    tools: Toolset | None = None
    guidance: str = ""
    hooks: HookChain = HookChain()
    checkpoint: Callable[[Session], Awaitable[None]] | None = None
    files: ChatFileService | None = None
    server_instructions: Callable[[], Mapping[str, str]] | None = None
    """Each connected server's instructions now, by server id; `None` means no servers."""

    def request_messages(
        self, session: Session, context: Sequence[str] = (), *, sees_images: bool
    ) -> list[Message]:
        """The request for `session`, with the step hooks' `context`; images only for a seer."""
        derived = derive_messages(session.events())
        history = derived if sees_images else without_images(derived)
        history = [*_with_context(history, context), *self._approval_mode_reminder(session)]
        system = system_text(session, self.guidance)
        if not system:
            return history
        return [SystemMessage(content=system), *history]

    def approval_mode(self, session: Session) -> ApprovalMode:
        """The mode `session`'s next call runs under."""
        if self.tools is None:
            return MODE_WITHOUT_TOOLSET
        return self.tools.approval_mode(session)

    def approval_mode_switch(self, session: Session) -> ApprovalModeSwitch | None:
        """The switch since `session`'s last step start; `None` without one or without tools."""
        if self.tools is None:
            return None
        return session.approval_mode_switch_since_last_step(self.tools.default_mode)

    def _approval_mode_reminder(self, session: Session) -> list[Message]:
        """The current mode as one system-reminder, once the person has switched this chat."""
        events = session.events()
        if self.tools is None or not any(isinstance(e, ApprovalModeChanged) for e in events):
            return []
        sentence = APPROVAL_MODE_SENTENCES[self.approval_mode(session)]
        return [UserMessage(content=SYSTEM_REMINDER.format(text=sentence))]

    async def run(
        self,
        user_input: str,
        *,
        session: Session,
        bot_id: str,
        files: tuple[ChatFile, ...] = (),
    ) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person: its events as they happen, then exactly one terminal."""
        _skip_calls_walked_past(session)
        turn = self._open_turn(session, bot_id)
        images = self.images.of_attachments(files) if await self.sees_images(bot_id) else ()
        message = UserMessage(content=user_input, images=images)
        session.append(UserMessageEvent(turn=turn, message=message, files=files))
        async with aclosing(run_turn(self, session, turn, bot_id=bot_id)) as events:
            async for event in events:
                yield event

    async def sees_images(self, bot_id: str) -> bool:
        """Whether `bot_id`'s model can be shown images now; `False` when it has none."""
        choice = await self.models.model_for(bot_id)
        return isinstance(choice, ModelChoice) and choice.vision

    async def hear(
        self, message: HeardMessage, *, session: Session, bot_id: str
    ) -> AsyncIterator[TurnEvent]:
        """A turn opened by a bot's message or a schedule: its events, then one terminal."""
        _skip_calls_walked_past(session)
        turn = self._open_turn(session, bot_id)
        session.append(_opening_event(turn, message))
        async with aclosing(run_turn(self, session, turn, bot_id=bot_id)) as events:
            async for event in events:
                yield event

    async def speak(self, *, session: Session, bot_id: str) -> AsyncIterator[TurnEvent]:
        """A turn opened for the next bot in line, with no new message from the person."""
        turn = self._open_turn(session, bot_id)
        async with aclosing(run_turn(self, session, turn, bot_id=bot_id)) as events:
            async for event in events:
                yield event

    async def resume(
        self, call_id: str, answer: Ok | Failure | Approval, *, session: Session, bot_id: str
    ) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person's answer to a client tool, or their approval of a call."""
        turn = self._open_turn(session, bot_id)
        if self.checkpoint is not None:
            await self.checkpoint(session)
        try:
            if isinstance(answer, Approval):
                call = _waiting_call(session, call_id)
                if answer.scope == "conversation":
                    session.append(ApprovalGrant(turn=turn, tool=call.name))
                async with aclosing(
                    run_approved_call(self, call, session=session, turn=turn, bot_id=bot_id)
                ) as events:
                    async for event in events:
                        yield event
            else:
                session.append(settled_result(call_id, answer, turn=turn, step=0))
            waiting = unanswered(session.events())
            if waiting:
                session.append(TurnEnd(turn=turn, reason="pending"))
                yield AgentPending(tool_call_id=waiting[0][1].id, name=waiting[0][1].name)
                return
        except BaseException:
            session.append(TurnEnd(turn=turn, reason="cancelled"))
            raise
        async with aclosing(run_turn(self, session, turn, bot_id=bot_id)) as events:
            async for event in events:
                yield event

    def _open_turn(self, session: Session, bot_id: str) -> int:
        """Append the next turn's start, then any server instructions that changed since logged."""
        turn = session.next_turn()
        session.append(TurnStart(turn=turn, bot_id=bot_id))
        if self.server_instructions is not None:
            for event in _changed(session.server_instructions(), self.server_instructions()):
                session.append(event)
        return turn

    async def compact(self, *, session: Session) -> AsyncIterator[CompactionEvent]:
        """A manual compaction, driven as its own run."""
        try:
            check_can_compact(session)
        except CompactionRefused:
            return
        async with aclosing(run_compaction(self, session, turn=None, trigger="manual")) as events:
            async for event in events:
                yield event


def _with_context(history: list[Message], context: Sequence[str]) -> list[Message]:
    """`history` with each `context` text as a system-reminder on its first user message."""
    if not context:
        return history
    for at, message in enumerate(history):
        if isinstance(message, UserMessage):
            reminders = [SYSTEM_REMINDER.format(text=text) for text in context]
            content = "\n\n".join([message.content, *reminders])
            reminded = message.model_copy(update={"content": content})
            return [*history[:at], reminded, *history[at + 1 :]]
    return history


def _changed(
    logged: Mapping[str, str], current: Mapping[str, str]
) -> list[ServerInstructionsEvent]:
    """An event for each server whose `current` instructions, absent meaning empty, differ."""
    servers = [*current, *(server for server in logged if server not in current)]
    return [
        ServerInstructionsEvent(server=server, instructions=current.get(server, ""))
        for server in servers
        if logged.get(server, "") != current.get(server, "")
    ]


def _skip_calls_walked_past(session: Session) -> None:
    """Answer every unanswered client call with `SKIPPED`, under the step that asked."""
    for asked, call in unanswered(session.events()):
        session.append(
            ToolResultEvent(
                turn=asked.turn,
                step=asked.step,
                message=ToolMessage(tool_call_id=call.id, content=SKIPPED_RESULT),
                error=SKIPPED,
            )
        )


def _waiting_call(session: Session, call_id: str) -> ToolCall:
    """The unanswered call the person approved; `LookupError` when the log holds no such call."""
    for _asked, call in unanswered(session.events()):
        if call.id == call_id:
            return call
    raise LookupError(f"no unanswered call {call_id!r}")


def _opening_event(
    turn: int, message: HeardMessage
) -> BotMessageEvent | ScheduleReminderEvent | TicketReportEvent:
    """The event that logs what opened turn `turn`."""
    if isinstance(message, BotMessage):
        return BotMessageEvent(turn=turn, message=message)
    if isinstance(message, TicketReport):
        return TicketReportEvent(turn=turn, report=message)
    return ScheduleReminderEvent(turn=turn, reminders=message.reminders)
