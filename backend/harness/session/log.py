"""The append-only log, and the session that owns one.

This class stays free of storage concerns: a backend's job is to persist exactly
what `append` recorded, and `SessionService` owns the cursor of how much of it is
durable. Nothing here knows whether anything is written down.

Two properties everything downstream leans on:

- **Append-only.** Nothing rewrites or removes an event. Compaction, when it
  arrives, appends a boundary rather than editing history; a UI's undo would be
  a new event too. It is what makes a sequence number a stable cursor.
- **Contiguous sequence numbers**, starting at 0, with no gaps. A consumer that
  has seen through `n` can ask for everything after `n` and know it missed
  nothing — which is how the phase-4 run subscription works.

`next_turn()` rather than a caller-supplied number: the log is the only thing
that knows how many turns it has, and letting a caller pass one invites two
concurrent turns to share an index and interleave.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness.session.models import SessionEvent, SessionHeader, TurnStart


class Session:
    """One agent interaction: an append-only event log plus its header."""

    def __init__(self, header: SessionHeader, events: Sequence[SessionEvent] = ()) -> None:
        self.header = header
        self._events: list[SessionEvent] = list(events)

    @property
    def id(self) -> str:
        """The session's identity, read from the header.

        A property rather than a second field, so a session and its stored
        metadata cannot disagree about which session this is.
        """
        return self.header.id

    def append(self, event: SessionEvent) -> int:
        """Record one event.

        @returns its sequence number — the index, which is also a stable cursor.
        """
        self._events.append(event)
        return len(self._events) - 1

    def events(self) -> Sequence[SessionEvent]:
        """Every event, oldest first.

        A view rather than a copy: callers read, and copying the whole log on
        each of the loop's per-step reads would make history derivation
        quadratic in a long conversation.
        """
        return self._events

    def next_turn(self) -> int:
        """The index the next turn should open with.

        Derived from the log rather than a counter, so a session rehydrated from
        storage (phase 3) resumes its numbering with no state to restore.
        """
        return sum(1 for event in self._events if isinstance(event, TurnStart))
