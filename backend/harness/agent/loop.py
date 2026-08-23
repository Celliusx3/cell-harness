"""`LoopAgent` — one turn: assemble a request, stream the reply, record both.

Phase 1 has no tools, so a turn is exactly one model call. The structure is
already the one phase 2 grows into: a turn opens, does work, and closes with a
reason, and every model-visible fact reaches the log on the way.

**The discipline this file exists to hold:** history comes from
`derive_messages(session.events())`, computed fresh before the request — never
from a list this class accumulated. Resume, fork, and compaction are all free
consequences of that; an accumulated list makes each of them a rewrite of this
module.

The system prompt is deliberately not logged and not part of history. It is
prepended per request, which is what lets it reflect the agent running *this*
turn — including, from phase 9, a different agent after routing.

`LoopAgent` is a frozen dataclass and holds no state: the `Session` passed to
`run()` owns everything that survives the call. Engine and state holder are
separate objects, so running a turn twice against two sessions cannot interleave.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass

from harness.agent.events import AgentCompleted, AgentFailed
from harness.llm.client import LLMClient
from harness.llm.messages import AssistantMessage, Message, SystemMessage, UserMessage
from harness.llm.stream import Completed, Failed, TextChunk
from harness.session.derive import derive_messages
from harness.session.events import (
    AssistantChunk,
    AssistantMessageEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.log import Session

# What a stream that produced no terminal event is reported as. An adapter owes
# exactly one (see `llm.client`); treating a missing one as a failure is how that
# contract is enforced rather than merely documented — the alternative is a turn
# that reports success having never heard from the model.
NO_TERMINAL = "stream ended without a terminal event"


@dataclass(frozen=True)
class LoopAgent:
    """An agent that answers with a single model call."""

    name: str
    model: str
    client: LLMClient
    system_prompt: str = ""

    def _request_messages(self, session: Session) -> list[Message]:
        """What this call sees: the system prompt, then the conversation.

        Derived at call time, so it already contains the user message appended a
        moment ago and every earlier turn, in log order.
        """
        history = derive_messages(session.events())
        if not self.system_prompt:
            return history
        return [SystemMessage(content=self.system_prompt), *history]

    async def run(
        self, user_input: str, *, session: Session
    ) -> AsyncIterator[TextChunk | AgentCompleted | AgentFailed]:
        """Run one turn, streaming its events.

        Yields the reply's `TextChunk`s live, then exactly one terminal. Calling
        it again continues the conversation — the log carries everything, so
        there is nothing else to thread between turns.
        """
        turn = session.next_turn()
        session.append(TurnStart(turn=turn))
        session.append(UserMessageEvent(turn=turn, message=UserMessage(content=user_input)))
        messages = self._request_messages(session)

        # Text streamed but not yet written to history. The log normally gains an
        # assistant message only when a call *completes*, so without this every
        # way a turn can end early would discard the half-answer the user watched
        # appear. The `finally` below is what rescues it.
        partial = ""
        # Whether this turn already recorded its own `turn/end`. The `finally`
        # runs on every path, including the orderly ones, and a turn closed twice
        # is a log that contradicts itself.
        closed = False

        try:
            completed: Completed | None = None
            failed: Failed | None = None

            # `aclosing`, not a bare `async for`: when this generator is closed
            # mid-stream, GeneratorExit unwinds *this* frame but would leave the
            # adapter's frame to the garbage collector's asyncgen hook — with the
            # HTTP response still open in the meantime.
            async with aclosing(self.client.stream_completion(messages, self.model)) as stream:
                async for event in stream:
                    # Every stream event is logged verbatim, terminals included:
                    # the log reproduces the stream, with no special cases to get
                    # wrong. `assistant/message` beside it is the assembled
                    # convenience, not a second source of truth.
                    session.append(AssistantChunk(turn=turn, chunk=event))
                    if isinstance(event, TextChunk):
                        partial += event.text
                        yield event
                    elif isinstance(event, Completed):
                        completed = event
                    elif isinstance(event, Failed):
                        failed = event

            if failed is not None:
                # No `assistant/message`: the adapter discarded whatever it had,
                # and the chunks above already record what the user saw.
                session.append(TurnEnd(turn=turn, reason="failed"))
                closed = True
                yield AgentFailed(reason=failed.reason)
                return

            if completed is None:
                session.append(TurnEnd(turn=turn, reason="failed"))
                closed = True
                yield AgentFailed(reason=NO_TERMINAL)
                return

            session.append(
                AssistantMessageEvent(
                    turn=turn,
                    message=AssistantMessage(content=completed.full_text),
                    usage=completed.usage,
                )
            )
            session.append(TurnEnd(turn=turn, reason="completed"))
            closed = True
            yield AgentCompleted(text=completed.full_text)
        finally:
            # `finally` rather than an exception handler because the abandoned
            # paths are not raises of the same kind: closing this generator
            # raises GeneratorExit, cancelling the task consuming it raises
            # CancelledError, and neither is an `except Exception`.
            #
            # Nothing is awaited here — an async generator may not yield during
            # cleanup, and `append` is synchronous, so there is nothing to wait on.
            if not closed:
                if partial:
                    session.append(
                        AssistantMessageEvent(
                            turn=turn,
                            message=AssistantMessage(content=partial),
                            interrupted=True,
                        )
                    )
                # A turn with no streamed text records no assistant message at
                # all: there was nothing visible to preserve, and an empty one
                # would be indistinguishable from a model that replied with
                # silence.
                session.append(TurnEnd(turn=turn, reason="cancelled"))
