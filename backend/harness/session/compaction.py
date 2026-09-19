"""Compaction's events, and the folds that read them back."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from harness.llm.messages import ApplicationMessage

if TYPE_CHECKING:
    from harness.session.models import SessionEvent

PRUNED = "[old tool result cleared to save context; call the tool again if you still need it]"

CompactionTrigger = Literal["auto", "manual", "overflow"]


class CompactionStart(BaseModel):
    """A compaction is being attempted."""

    model_config = ConfigDict(frozen=True)

    type: Literal["compaction/start"] = "compaction/start"
    turn: int | None
    trigger: CompactionTrigger
    tokens: int | None = None


class CompactionEnd(BaseModel):
    """The attempt is over — as exactly one of two outcomes."""

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
    """The index of the last successful `compaction/end`, or `None` if never compacted."""
    for index in reversed(range(len(events))):
        event = events[index]
        if isinstance(event, CompactionEnd) and event.succeeded:
            return index
    return None


def tail_start(events: Sequence[SessionEvent]) -> int:
    """The index where the un-compacted tail begins."""
    since = boundary(events)
    return 0 if since is None else since + 1


def pruned_ids(events: Sequence[SessionEvent]) -> frozenset[str]:
    """Every call id whose result has been cleared by any prune event."""
    return frozenset(
        call_id
        for event in events
        if isinstance(event, CompactionPrune)
        for call_id in event.call_ids
    )


def open_start(events: Sequence[SessionEvent]) -> CompactionStart | None:
    """A `compaction/start` a crash left without its `compaction/end`, or `None`."""
    for event in reversed(events):
        if isinstance(event, CompactionEnd):
            return None
        if isinstance(event, CompactionStart):
            return event
    return None
