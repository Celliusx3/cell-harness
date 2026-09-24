"""Decides when to compact, and does it — by appending events to the log."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from harness.agent.compaction.history import prunable, retained_skills, summarizable
from harness.agent.compaction.prompt import INSTRUCTION, render
from harness.llm.client import LLMClient
from harness.llm.messages import ApplicationMessage, SystemMessage, UserMessage
from harness.llm.stream import Completed, Failed
from harness.session.compaction import (
    CompactionEnd,
    CompactionPrune,
    CompactionStart,
    CompactionTrigger,
)
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.repair import unanswered

logger = logging.getLogger("harness.agent")

COMPACT_AT = 0.8

NOTHING = "nothing to compact"
UNANSWERED = "a client request is still unanswered"
INTERRUPTED = "interrupted"

CompactionEvent = CompactionStart | CompactionEnd | CompactionPrune


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

    def should_compact(self, session: Session) -> bool:
        """Is the context past the line?"""
        if self.context_tokens is None:
            return False
        used = session.context_size()
        return used is not None and used >= int(self.context_tokens * COMPACT_AT)

    def refusal_reason(self, session: Session) -> str | None:
        """Why a compaction cannot run now, for the manual path, or `None`."""
        events = session.events()
        if unanswered(events):
            return UNANSWERED
        if not prunable(events) and not summarizable(events):
            return NOTHING
        return None

    async def compact(
        self, session: Session, *, turn: int | None, trigger: CompactionTrigger
    ) -> AsyncIterator[CompactionEvent]:
        """One pass: prune if anything is prunable, else summarize inside a start/end bracket."""
        events = session.events()
        if ids := prunable(events):
            prune = CompactionPrune(turn=turn, call_ids=ids)
            session.append(prune)
            yield prune
            return
        if not summarizable(events):
            return
        start = CompactionStart(turn=turn, trigger=trigger, tokens=session.context_size())
        session.append(start)
        ended = False
        try:
            yield start
            end = await self._summarize(session, turn=turn)
            session.append(end)
            ended = True
            yield end
        finally:
            if not ended:
                session.append(CompactionEnd(turn=turn, error=INTERRUPTED))

    async def _summarize(self, session: Session, *, turn: int | None) -> CompactionEnd:
        """One model call, no tools; every way it can go wrong is an `error` end."""
        messages = [
            SystemMessage(content=self.system_prompt),
            *derive_messages(session.events()),
            UserMessage(content=INSTRUCTION),
        ]
        completed: Completed | None = None
        try:
            async for event in self.client.stream_completion(messages, self.model, tools=None):
                if isinstance(event, Failed):
                    return CompactionEnd(turn=turn, error=f"summary request failed: {event.reason}")
                if isinstance(event, Completed):
                    completed = event
        except Exception as err:
            logger.exception("compaction summarizer raised")
            return CompactionEnd(turn=turn, error=f"summarizer raised: {err}")
        if completed is None:
            return CompactionEnd(turn=turn, error="summary request produced no reply")
        text = completed.full_text.strip()
        if not text:
            return CompactionEnd(turn=turn, error="summary request produced no text")
        content = render(text, retained_skills(session.events()))
        return CompactionEnd(turn=turn, message=ApplicationMessage(content=content))
