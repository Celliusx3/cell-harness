"""`LoopAgent` — gather context, act, repeat until nothing is owed.

One **step** is one model request plus the tools it asked for. A **turn** is one
or more steps: if a step ends with tool calls, their results are appended and the
model is asked again; if it ends without, the turn is over. The steps are
`turn.py`'s; this module is how a turn *opens*, and there are two ways:

- `run(user_input)` — the person said something. Any call the log still
  holds unanswered is first answered as **skipped**: the person moved on. A
  provider refuses a history with a call and no result, so the line is not
  optional; and it is honest — the model asked, and nobody answered.
- `resume(call_id, outcome)` — the person answered a client tool. The turn
  opens with that result instead of a user message, and the model continues
  from where it stopped.

History comes from `derive_messages(session.events())`, recomputed before every
step — never from a list this class accumulated. That is what makes resume,
fork, and compaction consequences of the log, and it means a tool result reaches
the next request by being *logged*. The system prompt is prepended per request
and never logged, so it can reflect the agent running *this* turn.

`LoopAgent` is frozen and holds no state: the `Session` passed in owns
everything that survives the call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass

from harness.agent.compaction import CompactionService
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

# The result a client-tool call gets when the person continued without
# answering it. Written for the model: it must neither retry nor wait.
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
    # Asked before and after every tool call. Empty by default: the composition
    # root decides what is installed, and the loop does not know what it is.
    hooks: HookChain = HookChain()
    # Makes the log durable before each model request and each tool call — the
    # two moments a lost write would leave the log unable to explain what followed.
    checkpoint: Callable[[Session], Awaitable[None]] | None = None
    # Shrinks the history when it outgrows the window — before each request, and
    # as the net when the provider refuses one. `None` leaves the loop
    # uncompacted, the same way an empty `HookChain` leaves it unhooked.
    compaction: CompactionService | None = None

    def request_messages(self, session: Session) -> list[Message]:
        history = derive_messages(session.events())
        if not self.system_prompt:
            return history
        return [SystemMessage(content=self.system_prompt), *history]

    async def run(self, user_input: str, *, session: Session) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person: the reply's chunks live, tool progress
        and results as they settle, then exactly one terminal."""
        # After `repair`, the only unanswered calls are a pending turn's — the
        # ones the person is now walking past. Stamped with the call they
        # answer, so the log reads as the wire does: result under request.
        for asked, call in unanswered(session.events()):
            session.append(
                ToolResultEvent(
                    turn=asked.turn,
                    step=asked.step,
                    message=ToolMessage(tool_call_id=call.id, content=SKIPPED_RESULT),
                    error=SKIPPED,
                )
            )
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        session.append(UserMessageEvent(turn=turn, message=UserMessage(content=user_input)))
        # `aclosing`: a consumer closing this generator must close the turn's
        # too, or its `finally` — the one that answers owed calls — runs late.
        async with aclosing(drive(self, session, turn)) as events:
            async for event in events:
                yield event

    async def resume(
        self, call_id: str, outcome: Ok | Failure, *, session: Session
    ) -> AsyncIterator[TurnEvent]:
        """A turn opened by the person's answer to a client tool.

        The result is the first event of the new turn, and the request it
        builds carries `assistant(tool_calls) → tool(result)` — the sequence a
        provider requires — because `derive_messages` ignores turn boundaries.
        The caller has checked, against the log, that `call_id` is the one
        pending call; this only writes what it is given.
        """
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
        # `aclosing`: a consumer closing this generator must close the turn's
        # too, or its `finally` — the one that answers owed calls — runs late.
        async with aclosing(drive(self, session, turn)) as events:
            async for event in events:
                yield event

    async def compact(self, *, session: Session) -> AsyncIterator[object]:
        """A manual compaction, driven as its own run. Yields the compaction
        events so the run's stream wakes subscribers as they land; appends
        nothing when the service refuses (`compact_now` checks first)."""
        async with aclosing(self.compaction.compact_now(session)) as events:  # type: ignore[union-attr]
            async for event in events:
                yield event
