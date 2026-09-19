"""Decides when to compact, and does it — by appending events to the log."""

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

COMPACT_AT = 0.8

NOTHING = "nothing to compact"
UNANSWERED = "a client request is still unanswered"
INTERRUPTED = "interrupted"


class CompactionRefused(Exception):
    """A manual compaction cannot run now."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CompactionService:
    """Summarizes and prunes a session's history, in place, as events."""

    client: LLMClient
    model: str
    system_prompt: str
    context_tokens: int | None

    def due(self, session: Session) -> bool:
        """Is the context past the line?"""
        if self.context_tokens is None:
            return False
        used = session.context_size()
        return used is not None and used >= int(self.context_tokens * COMPACT_AT)

    def refusal(self, session: Session) -> str | None:
        """Why a compaction cannot run now, for the manual path, or `None`."""
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
        """A manual compaction: nothing when refused, else one reduce pass."""
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
        """Does the un-compacted tail hold a user message to summarize?"""
        events = session.events()
        return any(e.type == "user/message" for e in events[tail_start(events) :])

    async def _summarize(
        self, session: Session, *, turn: int | None, trigger: CompactionTrigger
    ) -> AsyncIterator[CompactionStart | CompactionEnd]:
        """The bracket's lifecycle: open, summarize, close."""
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
            if not ended:
                session.append(CompactionEnd(turn=turn, error=INTERRUPTED))

    async def _finish(self, session: Session, *, turn: int | None) -> CompactionEnd:
        """The summary as one `CompactionEnd`: success with a message, or failure with a reason."""
        try:
            summary = await self._ask(session)
        except _SummaryFailed as failed:
            return CompactionEnd(turn=turn, error=str(failed))
        except Exception as err:
            logger.exception("compaction summarizer raised")
            return CompactionEnd(turn=turn, error=f"summarizer raised: {err}")
        message = ApplicationMessage(content=render(summary, retained_skills(session.events())))
        return CompactionEnd(turn=turn, message=message)

    async def _ask(self, session: Session) -> str:
        """One model call: the conversation as the model sees it, plus the instruction, no tools."""
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
