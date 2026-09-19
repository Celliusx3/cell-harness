"""`LoopAgent` — gather context, act, repeat until nothing is owed."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass

from harness.agent.compaction import CompactionRefused, CompactionService
from harness.agent.hooks import HookChain
from harness.agent.turn import TurnEvent, drive
from harness.llm.client import LLMClient
from harness.llm.messages import Message, SystemMessage, ToolMessage, UserMessage
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.models import ToolResultEvent, TurnStart, UserMessageEvent
from harness.session.repair import unanswered
from harness.tools.definition import ERROR_PREFIX, Failure, Ok, render_outcome
from harness.tools.pipeline import ToolPipeline

SKIPPED = "SKIPPED"
SKIPPED_RESULT = (
    f"{ERROR_PREFIX}the user continued without answering this; do not ask again "
    "unless they return to it, and do not wait for it."
)


@dataclass(frozen=True)
class LoopAgent:
    """An agent that answers by running the tool loop."""

    name: str
    model: str
    client: LLMClient
    tools: ToolPipeline | None = None
    system_prompt: str = ""
    hooks: HookChain = HookChain()
    checkpoint: Callable[[Session], Awaitable[None]] | None = None
    compaction: CompactionService | None = None

    def request_messages(self, session: Session) -> list[Message]:
        history = derive_messages(session.events())
        if not self.system_prompt:
            return history
        return [SystemMessage(content=self.system_prompt), *history]

    async def run(self, user_input: str, *, session: Session) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person: its events as they happen, then exactly one terminal."""
        _skip_calls_walked_past(session)
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        session.append(UserMessageEvent(turn=turn, message=UserMessage(content=user_input)))
        async with aclosing(drive(self, session, turn)) as events:
            async for event in events:
                yield event

    async def resume(
        self, call_id: str, outcome: Ok | Failure, *, session: Session
    ) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person's answer to a client tool."""
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        content = render_outcome(outcome)
        session.append(
            ToolResultEvent(
                turn=turn,
                step=0,
                message=ToolMessage(tool_call_id=call_id, content=content),
                error=None if isinstance(outcome, Ok) else outcome.code,
                ui=outcome.ui if isinstance(outcome, Ok) else None,
            )
        )
        async with aclosing(drive(self, session, turn)) as events:
            async for event in events:
                yield event

    async def compact(self, *, session: Session) -> AsyncIterator[object]:
        """A manual compaction, driven as its own run."""
        if self.compaction is None:
            raise CompactionRefused("compaction is not configured")
        async with aclosing(self.compaction.compact_now(session)) as events:
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
