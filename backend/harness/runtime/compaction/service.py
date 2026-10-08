"""Decides when to compact, and does it — by appending events to the log."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from harness.llm.messages import ApplicationMessage, UserMessage
from harness.llm.stream import Completed, Failed
from harness.runtime.compaction.history import loaded_skills, prunable_ids, summarizable
from harness.runtime.compaction.prompt import INSTRUCTION, summary_message
from harness.session.compaction import (
    CompactionEnd,
    CompactionPrune,
    CompactionStart,
    CompactionTrigger,
)
from harness.session.log import Session
from harness.session.repair import unanswered

if TYPE_CHECKING:
    from harness.runtime.service import Runtime

logger = logging.getLogger("harness.runtime")

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


def check_can_compact(session: Session) -> None:
    """Raise `CompactionRefused` with the reason when a manual compaction cannot run now."""
    events = session.events()
    if unanswered(events):
        raise CompactionRefused(UNANSWERED)
    if not prunable_ids(events) and not summarizable(events):
        raise CompactionRefused(NOTHING)


def should_compact(runtime: Runtime, session: Session) -> bool:
    """Is the context past the line?"""
    if runtime.context_tokens is None:
        return False
    used = session.context_size()
    return used is not None and used >= int(runtime.context_tokens * COMPACT_AT)


async def run_compaction(
    runtime: Runtime, session: Session, *, turn: int | None, trigger: CompactionTrigger
) -> AsyncIterator[CompactionEvent]:
    """One pass: prune if anything is prunable, else summarize inside a start/end bracket."""
    events = session.events()
    if ids := prunable_ids(events):
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
        end = await _summarize(runtime, session, turn=turn)
        session.append(end)
        ended = True
        yield end
    finally:
        if not ended:
            session.append(CompactionEnd(turn=turn, error=INTERRUPTED))


async def _summarize(runtime: Runtime, session: Session, *, turn: int | None) -> CompactionEnd:
    """One model call, no tools; every way it can go wrong is an `error` end."""
    messages = [*runtime.request_messages(session), UserMessage(content=INSTRUCTION)]
    completed: Completed | None = None
    try:
        async for event in runtime.client.stream_completion(messages, runtime.model, tools=None):
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
    content = summary_message(text, loaded_skills(session.events()))
    return CompactionEnd(turn=turn, message=ApplicationMessage(content=content))
