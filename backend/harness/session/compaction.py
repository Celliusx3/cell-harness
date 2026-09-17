"""Compaction's events, and the folds that read them back.

Compaction **appends**; it never rewrites. When the context grows past what the
model should carry, the loop first clears old tool results from the model's
view, and when that is not enough, summarizes what came before into one
message the model reads instead. Both are events here, and `derive_messages`
is where they take effect — the file keeps every original line, so a sequence
number stays a cursor and the browser still shows the whole conversation.

Two events bracket a summary, the way `turn/start` and `turn/end` bracket a
turn: `compaction/start` says one is being attempted and with what trigger,
`compaction/end` carries the summary — or the error, when the summarizer did
not deliver. A failed end is a fact about the conversation, like a failed
turn, and it is **not** a boundary. dsh writes three events; the summary rides
on the end here the way `usage` rides on the assistant message.

`compaction/prune` is Claude Code's cleared tool-use ids: the results named
render as a placeholder from then on. A `skill` result is never named — a
loaded skill is behavioural guidance, and losing it degrades the agent with no
visible error.

Pure: no I/O, and nothing from `repository`. The layering test enforces it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from harness.llm.messages import ApplicationMessage

if TYPE_CHECKING:
    from harness.session.models import SessionEvent

# What the model reads in place of a cleared result. Says what to do, because a
# model told only "[cleared]" has been seen to ask the person what the tool said.
PRUNED = "[old tool result cleared to save context; call the tool again if you still need it]"

# `auto`: the size check before a step. `manual`: the person asked. `overflow`:
# the provider refused the request — the net under the check.
CompactionTrigger = Literal["auto", "manual", "overflow"]


class CompactionStart(BaseModel):
    """A compaction is being attempted. `turn` is `None` for a manual one on an
    idle conversation; `tokens` is the size that triggered it, when known."""

    model_config = ConfigDict(frozen=True)

    type: Literal["compaction/start"] = "compaction/start"
    turn: int | None
    trigger: CompactionTrigger
    tokens: int | None = None


class CompactionEnd(BaseModel):
    """The attempt is over — as exactly one of two outcomes.

    A success carries `message`: what the model reads from here on, logged
    verbatim so the UI shows the same words. A failure carries `error`: an
    attempt that changed nothing, a fact like a failed turn. The validator
    makes the pair a real sum type — both-set or neither-set cannot be built —
    so `succeeded` is the one thing to read, never `message is not None` at
    three call sites that might drift.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["compaction/end"] = "compaction/end"
    turn: int | None
    message: ApplicationMessage | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _one_outcome(self) -> CompactionEnd:
        if (self.message is None) == (self.error is None):
            raise ValueError("a compaction/end carries exactly one of message or error")
        return self

    @property
    def succeeded(self) -> bool:
        """A boundary was written — the model's history now starts here."""
        return self.message is not None


class CompactionPrune(BaseModel):
    """These results are cleared from the model's view."""

    model_config = ConfigDict(frozen=True)

    type: Literal["compaction/prune"] = "compaction/prune"
    turn: int | None
    call_ids: tuple[str, ...]


def boundary(events: Sequence[SessionEvent]) -> int | None:
    """The index of the last successful `compaction/end`, or `None` when the
    conversation has never been compacted. Scanned newest-first so a long log
    stops at the boundary near its end rather than reading to the start."""
    for index in reversed(range(len(events))):
        event = events[index]
        if isinstance(event, CompactionEnd) and event.succeeded:
            return index
    return None


def tail_start(events: Sequence[SessionEvent]) -> int:
    """The index where the un-compacted tail begins: just past the boundary, or
    `0` when there is none. The one place that turns `boundary`'s optional index
    into a slice start, so no caller repeats `... if since is not None else 0`."""
    since = boundary(events)
    return 0 if since is None else since + 1


def pruned_ids(events: Sequence[SessionEvent]) -> frozenset[str]:
    """Every call whose result has been cleared, unioned across all prune
    events — a result cleared once stays cleared."""
    return frozenset(
        call_id
        for event in events
        if isinstance(event, CompactionPrune)
        for call_id in event.call_ids
    )


def open_start(events: Sequence[SessionEvent]) -> CompactionStart | None:
    """A `compaction/start` a crash left without its `compaction/end`, or `None`.

    The newest bracket event decides: reading back from the end, a `start` seen
    before any `end` is still open; an `end` seen first means the last bracket
    already closed.
    """
    for event in reversed(events):
        if isinstance(event, CompactionEnd):
            return None
        if isinstance(event, CompactionStart):
            return event
    return None
