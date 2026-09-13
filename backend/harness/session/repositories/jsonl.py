"""A session repository backed by one append-only JSONL file per session.

    <root>/<session-id>.jsonl
      line 1   {"type":"session","version":1,"id":…,"created_at":…,"title":…}
      line 2+  one SessionEvent per line; the event on line n has seq n - 2

`list()` reads **only line 1** of each file. That is what makes a directory of
JSONL files a perfectly good conversation index, and it is why this is JSONL
rather than SQLite — a database earns its place when we need to search message
*content*, not to list conversations. When that day comes, a
`SqliteSessionRepository` implements the same `SessionRepository` Protocol and
the service above it does not change.

Modelled on DeepSeek Harness's `session-persistence-jsonl`, minus its zstd
frames, packed chunk rows, project directories, and write batching. Those are
optimizations at a scale we do not have; none of them changes the contract.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from harness.session.models import (
    SESSION_FORMAT_VERSION,
    SessionEvent,
    SessionHeader,
    UserMessageEvent,
)
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)

# How many characters of the first user message become the title. Long enough to
# tell two conversations apart in a list, short enough to render in a sidebar.
# The full message is always in the log; this is a label, not a summary.
TITLE_MAX_CHARS = 120

# Built once: constructing a TypeAdapter is not free, and this decodes every
# line of every log. The discriminated union resolves on `type`, and the
# header's slash-less `"session"` tag matches no event type — so a misread line
# fails loudly instead of decoding as the wrong thing.
_EVENT = TypeAdapter(SessionEvent)


def _title_from(events: Sequence[SessionEvent]) -> str:
    """A label taken from the conversation's first user message.

    Stamped once, at first append, which is the only moment the header is
    written — so it costs nothing and needs no later rewrite of a file that is
    append-only by design.
    """
    for event in events:
        if isinstance(event, UserMessageEvent) and event.source == "user":
            text = event.message.content.strip()
            if text:
                return text[:TITLE_MAX_CHARS]
    return ""


class JsonlSessionRepository:
    """Stores sessions as one append-only JSONL file each."""

    def __init__(self, root: Path) -> None:
        self._root = root
        # Headers of sessions created but not yet appended to. They have no file
        # (see `create`), so this is the only place their metadata lives.
        self._pending: dict[str, SessionHeader] = {}
        # Events on disk per session — a memo, not a second source of truth.
        #
        # `stored_count` is asked on every flush, and a flush happens before
        # every model request and every tool dispatch: ~40 times in a long turn.
        # Counting the file each time is O(size) per call on a file that grows
        # with the conversation, so it compounds. Measured on a 165 KB log,
        # caching is ~220x.
        #
        # It assumes **this process is the only writer**. True today: one CLI
        # process, and phase 4 is one server. A second writer would leave this
        # count stale and the next append would land at the wrong offset, so
        # multi-process access needs more than a bigger cache — it needs a lock,
        # and that is a decision for whoever first wants two writers.
        self._stored: dict[str, int] = {}

    def _path(self, session_id: str) -> Path:
        # Ids are ours (uuid4), so escaping is unnecessary — but a traversal
        # check costs nothing and means an id that ever becomes user-supplied
        # cannot reach outside the root.
        if "/" in session_id or "\\" in session_id or session_id in {".", ".."}:
            raise ValueError(f"unsafe session id {session_id!r}")
        return self._root / f"{session_id}.jsonl"

    async def create(self, header: SessionHeader) -> None:
        """Remember the header; write nothing.

        **Lazy materialization.** A session created and then abandoned — a UI
        that opened a blank conversation, a run that failed before its first
        event — leaves no file behind and never appears in `list`.
        """
        self._pending[header.id] = header

    async def stored_count(self, session_id: str) -> int:
        """Events already on disk. Counted from the file once, then remembered."""
        return self._count(session_id, self._path(session_id))

    async def append(self, session_id: str, events: Sequence[SessionEvent]) -> None:
        """Durably record a batch.

        Appends wherever the stored log currently ends — there is no `first_seq`
        to pass, because this object already knows and a caller repeating it
        would be a second copy of one fact.

        The first append writes header and batch together, atomically: a
        temporary file, fsynced, then renamed into place, so a crash mid-write
        never leaves a file with no header. Later appends extend the file and
        fsync; a failure truncates back to the prior length rather than leaving
        a half-written line committed.
        """
        if not events:
            return
        path = self._path(session_id)
        stored = self._count(session_id, path)
        self._root.mkdir(parents=True, exist_ok=True)
        if stored == 0 and not path.exists():
            header = self._pending.get(session_id)
            if header is None:
                raise SessionNotFoundError(f"session {session_id!r} was never created")
            titled = header.model_copy(update={"title": header.title or _title_from(events)})
            _write_first(path, titled, events)
            self._pending.pop(session_id, None)
        else:
            _append_lines(path, events)
        self._stored[session_id] = stored + len(events)

    def _count(self, session_id: str, path: Path) -> int:
        """Events on disk. Read from the file once per session, then remembered.

        A restarted process counts rather than assuming zero, which is what makes
        a resumed session append after its stored log instead of over the header.
        """
        if session_id in self._stored:
            return self._stored[session_id]
        count = 0 if not path.exists() else max(len(_read_lines(path)) - 1, 0)
        self._stored[session_id] = count
        return count

    async def load(self, session_id: str) -> tuple[SessionHeader, list[SessionEvent]]:
        """Read a session back, tolerating only a torn tail.

        A structurally incomplete **last** line is dropped: a crash mid-write can
        leave one, and everything before it was durably committed. Anything
        malformed earlier is `SessionCorruptionError` — that is a hole in the
        middle of a conversation, and quietly skipping it would send the model a
        history that silently disagrees with what happened.

        Returns the log **as stored**. Closing whatever a dead process left open
        is `repair.py`'s job, kept separate so a caller can read a raw log
        without mutating it.
        """
        path = self._path(session_id)
        if not path.exists():
            raise SessionNotFoundError(f"no stored session {session_id!r}")

        lines = _read_lines(path)
        if not lines:
            raise SessionCorruptionError(f"{path}: empty log, no header")

        header = _decode_header(lines[0], path)
        events: list[SessionEvent] = []
        body = lines[1:]
        for index, line in enumerate(body):
            try:
                events.append(_EVENT.validate_json(line))
            except (json.JSONDecodeError, ValidationError) as err:
                torn = index == len(body) - 1 and not line.endswith("\n")
                if torn:
                    # The process died mid-write. Everything before this line is
                    # intact and keeps its meaning.
                    break
                raise SessionCorruptionError(
                    f"{path}: line {index + 2} is unreadable and is not a torn final write: {err}"
                ) from err
        self._stored[session_id] = len(events)
        return header, events

    async def list(self) -> list[SessionHeader]:
        """Every stored session, newest first — reading only line 1 of each file.

        A log whose header is unreadable is skipped rather than raising: one
        corrupt file must not make the whole conversation list unopenable, and
        the error surfaces when that session is actually loaded.
        """
        if not self._root.exists():
            return []
        headers: list[SessionHeader] = []
        for path in sorted(self._root.glob("*.jsonl")):
            try:
                with open(path, encoding="utf-8") as handle:
                    first = handle.readline()
                headers.append(_decode_header(first, path))
            except (OSError, json.JSONDecodeError, ValidationError, SessionFormatUnsupportedError):
                continue
        return sorted(headers, key=lambda header: header.created_at, reverse=True)


def _encode(events: Sequence[SessionEvent]) -> str:
    return "".join(event.model_dump_json() + "\n" for event in events)


def _read_lines(path: Path) -> list[str]:
    """Lines with their terminators kept, so a torn final line is detectable."""
    with open(path, encoding="utf-8") as handle:
        return handle.readlines()


def _write_first(path: Path, header: SessionHeader, events: Sequence[SessionEvent]) -> None:
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(header.model_dump_json() + "\n")
        handle.write(_encode(events))
        handle.flush()
        os.fsync(handle.fileno())
    # `replace` rather than a hard link: atomic on POSIX and Windows alike, and
    # a leftover .tmp from an earlier crash must not block a fresh write.
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _append_lines(path: Path, events: Sequence[SessionEvent]) -> None:
    before = path.stat().st_size
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(_encode(events))
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # Roll back to the last known-good length, so a partial line never
        # becomes part of the committed log.
        with open(path, "r+b") as handle:
            handle.truncate(before)
            os.fsync(handle.fileno())
        raise


def _decode_header(line: str, path: Path) -> SessionHeader:
    data = json.loads(line)
    version = data.get("version")
    if version != SESSION_FORMAT_VERSION:
        raise SessionFormatUnsupportedError(
            f"{path}: format version {version!r}, this build reads "
            f"{SESSION_FORMAT_VERSION}. No migration exists; refusing rather than guessing."
        )
    return SessionHeader.model_validate(data)


def _fsync_dir(directory: Path) -> None:
    """Make a rename durable. A file can be fsynced and still vanish on power
    loss if its directory entry was never flushed."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        # Unsupported on some filesystems; the rename is still atomic, only its
        # durability window is wider.
        pass
    finally:
        os.close(fd)
