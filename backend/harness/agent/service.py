"""`Agent` — gather context, act, repeat until nothing is owed."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass

from harness.agent.compaction import (
    CompactionEvent,
    CompactionRefused,
    check_can_compact,
    run_compaction,
)
from harness.agent.events import AgentPending, TurnEvent
from harness.agent.hooks import HookChain
from harness.agent.system_prompt import system_text
from harness.agent.tool_run import run_approved_call, settled_result
from harness.agent.turn import run_turn
from harness.llm.client import LLMClient
from harness.llm.messages import Message, SystemMessage, ToolCall, ToolMessage, UserMessage
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.models import (
    ApprovalGrant,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repair import unanswered
from harness.tools.approval import Approved
from harness.tools.definition import ERROR_PREFIX, Failure, Ok
from harness.tools.pipeline import ToolPipeline

SKIPPED = "SKIPPED"
SKIPPED_RESULT = (
    f"{ERROR_PREFIX}the user continued without answering this; do not ask again "
    "unless they return to it, and do not wait for it."
)


@dataclass(frozen=True)
class Agent:
    """An agent that answers by running the tool loop."""

    model: str
    client: LLMClient
    tools: ToolPipeline | None = None
    guidance: str = ""
    hooks: HookChain = HookChain()
    checkpoint: Callable[[Session], Awaitable[None]] | None = None
    context_tokens: int | None = None

    def request_messages(self, session: Session) -> list[Message]:
        history = derive_messages(session.events())
        system = system_text(session, self.guidance)
        if not system:
            return history
        return [SystemMessage(content=system), *history]

    async def run(self, user_input: str, *, session: Session) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person: its events as they happen, then exactly one terminal."""
        _skip_calls_walked_past(session)
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        session.append(UserMessageEvent(turn=turn, message=UserMessage(content=user_input)))
        async with aclosing(run_turn(self, session, turn)) as events:
            async for event in events:
                yield event

    async def resume(
        self, call_id: str, answer: Ok | Failure | Approved, *, session: Session
    ) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person's answer to a client tool, or their approval of a call."""
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        if self.checkpoint is not None:
            await self.checkpoint(session)
        try:
            if isinstance(answer, Approved):
                call = _waiting_call(session, call_id)
                if answer.scope == "conversation":
                    session.append(ApprovalGrant(turn=turn, tool=call.name))
                async with aclosing(
                    run_approved_call(self, call, session=session, turn=turn)
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
        async with aclosing(run_turn(self, session, turn)) as events:
            async for event in events:
                yield event

    async def compact(self, *, session: Session) -> AsyncIterator[CompactionEvent]:
        """A manual compaction, driven as its own run."""
        try:
            check_can_compact(session)
        except CompactionRefused:
            return
        async with aclosing(run_compaction(self, session, turn=None, trigger="manual")) as events:
            async for event in events:
                yield event


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
