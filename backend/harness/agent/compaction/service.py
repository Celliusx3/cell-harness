"""Decides when to compact, and does it — by appending events to the log.

The one seam the loop holds. Everything it does is append events a fold reads
back: `derive_messages` honours the boundary, `prune` honours the cleared ids,
so the loop's own history shrinks with no second store. It never rewrites.

Three entry points, one body:
- `before_step` — the size check before every model request. Over the line, it
  prunes if it can (no model call), else summarizes.
- `recover` — the net under the check: the provider refused the request for its
  size. Same body, ignoring the line, and bounded because each pass strictly
  shrinks the derived history and a log that is only a summary has nothing left.
- `compact_now` — the person asked. Refuses out loud when there is nothing to
  do or a client request is unanswered, rather than writing an empty bracket.

It catches its own failures: a summarizer that raises, times out, or returns
nothing logs `compaction/end { error }` and the step proceeds unchanged. A
decision that must fail open — losing the turn to a summary bug is worse than
a big request — the same stance as the guardrail hooks.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass

from harness.agent.compaction.prompt import INSTRUCTION, render
from harness.agent.compaction.prune import prunable
from harness.agent.compaction.retain import retained_skills
from harness.llm.client import LLMClient
from harness.llm.messages import ApplicationMessage, SystemMessage, UserMessage
from harness.llm.stream import Completed, Failed
from harness.session.compaction import (
    CompactionEnd,
    CompactionPrune,
    CompactionStart,
    CompactionTrigger,
    tail_start,
)
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.repair import unanswered

logger = logging.getLogger("harness.agent")

# Compact at this fraction of the window. dsh's ratio; Claude Code's absolute
# 13k reserve is tuned to a 200k window and goes negative at 16k.
COMPACT_AT = 0.8

NOTHING = "nothing to compact"
UNANSWERED = "a client request is still unanswered"
# The close a cancelled or crashed bracket gets, so it is never left open.
INTERRUPTED = "interrupted"


class CompactionRefused(Exception):
    """A manual compaction cannot run now. `reason` is one of the strings
    above — safe to show a person, and what the route returns as a 409."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CompactionService:
    """Summarizes and prunes a session's history, in place, as events."""

    client: LLMClient
    model: str
    system_prompt: str
    # The model's context window: config, else discovered, else `None` —
    # proactive compaction off, the reactive net still on.
    context_tokens: int | None

    def due(self, session: Session) -> bool:
        """Is the context past the line? False when the window is unknown or
        nothing has been measured yet."""
        if self.context_tokens is None:
            return False
        used = session.context_size()
        return used is not None and used >= int(self.context_tokens * COMPACT_AT)

    def refusal(self, session: Session) -> str | None:
        """Why a compaction cannot run now, for the manual path, or `None`."""
        # A pending client call is an assistant message whose tool call has no
        # result — exactly what `unanswered` finds, and what a provider rejects.
        if unanswered(session.events()):
            return UNANSWERED
        if not prunable(session.events()) and not self._summarizable(session):
            return NOTHING
        return None

    async def before_step(
        self, session: Session, *, turn: int
    ) -> AsyncIterator[CompactionStart | CompactionEnd | CompactionPrune]:
        """The size check before a model request."""
        if self.due(session):
            async with aclosing(self._reduce(session, turn=turn, trigger="auto")) as events:
                async for event in events:
                    yield event

    async def recover(
        self, session: Session, *, turn: int
    ) -> AsyncIterator[CompactionStart | CompactionEnd | CompactionPrune]:
        """The provider refused the request. Reduce regardless of the line."""
        async with aclosing(self._reduce(session, turn=turn, trigger="overflow")) as events:
            async for event in events:
                yield event

    async def compact_now(
        self, session: Session
    ) -> AsyncIterator[CompactionStart | CompactionEnd | CompactionPrune]:
        """The person asked. Refuse silently here — the caller reports why via
        `refusal` — rather than write a bracket that changed nothing."""
        if self.refusal(session) is not None:
            return
        async with aclosing(self._reduce(session, turn=None, trigger="manual")) as events:
            async for event in events:
                yield event

    async def _reduce(
        self, session: Session, *, turn: int | None, trigger: CompactionTrigger
    ) -> AsyncIterator[CompactionStart | CompactionEnd | CompactionPrune]:
        """Prune if anything is prunable, else summarize. One pass."""
        ids = prunable(session.events())
        if ids:
            event = CompactionPrune(turn=turn, call_ids=ids)
            session.append(event)
            yield event
            return
        if not self._summarizable(session):
            return
        async with aclosing(self._summarize(session, turn=turn, trigger=trigger)) as events:
            async for event in events:
                yield event

    def _summarizable(self, session: Session) -> bool:
        """Is there anything before the tail worth summarizing — i.e. not
        already reduced to a lone summary? Bounds `recover`."""
        events = session.events()
        return any(e.type == "user/message" for e in events[tail_start(events) :])

    async def _summarize(
        self, session: Session, *, turn: int | None, trigger: CompactionTrigger
    ) -> AsyncIterator[CompactionStart | CompactionEnd]:
        """The bracket's lifecycle: open, summarize, close. `_finish` decides
        the outcome; this only guarantees a close, even on cancellation."""
        start = CompactionStart(turn=turn, trigger=trigger, tokens=session.context_size())
        session.append(start)
        ended = False
        try:
            yield start
            end = await self._finish(session, turn=turn)
            session.append(end)
            ended = True
            yield end
        finally:
            # GeneratorExit at either yield, or cancellation inside `_finish`:
            # the bracket is closed here so `repair` and the UI never see it open.
            if not ended:
                session.append(CompactionEnd(turn=turn, error=INTERRUPTED))

    async def _finish(self, session: Session, *, turn: int | None) -> CompactionEnd:
        """The summary as one outcome: a success end with the message, or a
        failure end with the reason. Fails open — a summarizer bug is a failed
        attempt, never a lost turn."""
        try:
            summary = await self._ask(session)
        except _SummaryFailed as failed:
            return CompactionEnd(turn=turn, error=str(failed))
        except Exception as err:  # noqa: BLE001 — a summarizer bug must not cost the turn
            logger.exception("compaction summarizer raised")
            return CompactionEnd(turn=turn, error=f"summarizer raised: {err}")
        message = ApplicationMessage(content=render(summary, retained_skills(session.events())))
        return CompactionEnd(turn=turn, message=message)

    async def _ask(self, session: Session) -> str:
        """One model call: the conversation as the model sees it, plus the
        instruction, no tools. Only text is kept."""
        messages = [
            SystemMessage(content=self.system_prompt),
            *derive_messages(session.events()),
            UserMessage(content=INSTRUCTION),
        ]
        completed: Completed | None = None
        async for event in self.client.stream_completion(messages, self.model, tools=None):
            if isinstance(event, Failed):
                raise _SummaryFailed(f"summary request failed: {event.reason}")
            if isinstance(event, Completed):
                completed = event
        if completed is None:
            raise _SummaryFailed("summary request produced no reply")
        text = completed.full_text.strip()
        if not text:
            raise _SummaryFailed("summary request produced no text")
        return text


class _SummaryFailed(Exception):
    """An expected, reported failure of the summary request."""
