"""A session repository backed by one append-only JSONL file per session."""

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
from harness.skills import display

TITLE_MAX_CHARS = 120

_EVENT = TypeAdapter(SessionEvent)


def _title_from(events: Sequence[SessionEvent]) -> str:
    """A label taken from the conversation's first user message."""
    for event in events:
        if isinstance(event, UserMessageEvent):
            content = event.message.content
            shown = display(content)
            text = (shown.typed if shown else content).strip()
            if text:
                return text[:TITLE_MAX_CHARS]
    return ""


class JsonlSessionRepository:
    """Stores sessions as one append-only JSONL file each."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._pending: dict[str, SessionHeader] = {}
        self._stored_count_single_writer: dict[str, int] = {}

    def _path(self, session_id: str) -> Path:
        if "/" in session_id or "\\" in session_id or session_id in {".", ".."}:
            raise ValueError(f"unsafe session id {session_id!r}")
        return self._root / f"{session_id}.jsonl"

    async def create(self, header: SessionHeader) -> None:
        """Remember the header; write nothing."""
        self._pending[header.id] = header

    async def stored_count(self, session_id: str) -> int:
        """Events already on disk. Counted from the file once, then remembered."""
        return self._count(session_id, self._path(session_id))

    async def append(self, session_id: str, events: Sequence[SessionEvent]) -> None:
        """Durably record a batch."""
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
        self._stored_count_single_writer[session_id] = stored + len(events)

    def _count(self, session_id: str, path: Path) -> int:
        """Events on disk."""
        if session_id in self._stored_count_single_writer:
            return self._stored_count_single_writer[session_id]
        count = 0 if not path.exists() else max(len(_read_lines(path)) - 1, 0)
        self._stored_count_single_writer[session_id] = count
        return count

    async def load(self, session_id: str) -> tuple[SessionHeader, list[SessionEvent]]:
        """Read a session back, tolerating only a torn tail."""
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
                    break
                raise SessionCorruptionError(
                    f"{path}: line {index + 2} is unreadable and is not a torn final write: {err}"
                ) from err
        self._stored_count_single_writer[session_id] = len(events)
        return header, events

    async def list(self) -> list[SessionHeader]:
        """Every stored session, newest first — reading only line 1 of each file."""
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
    """Make a rename durable."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        # Directory fsync is unsupported on some filesystems; the rename stays atomic.
        pass
    finally:
        os.close(fd)
