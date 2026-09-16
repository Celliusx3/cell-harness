"""Chat state as one JSON file per chat, plus one cursor file per channel.

A whole-file rewrite per save, unlike the session log's append. The two have
opposite shapes: a session grows without bound and is never rewritten, while a
chat's state is a handful of fields *replaced* every time. Appending mutations
here would mean replaying them on load to learn one small record.

Every write is atomic — temp file, fsync, rename — so a crash mid-save leaves the
previous state rather than a truncated one. Losing a `delivered_through` update
means re-sending one message; losing the *file* would mean re-sending everything.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from harness.channels.repository import ChatState, ChatStateError

# Chat ids reach us from a remote platform, and they end up in a filename. A
# WhatsApp id is a phone number, a Slack one is `C01ABC`, and neither should ever
# be able to contain a path separator — so anything outside this set is escaped
# rather than trusted.
_SAFE = re.compile(r"[^A-Za-z0-9_-]")


class JsonlChatRepository:
    """Per-chat JSON files under one directory."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, channel: str, chat_id: str) -> Path:
        # The channel is part of the name, not just the contents: Telegram chat
        # `123` and Discord channel `123` are different conversations and must
        # not share a file.
        return self._root / f"{_safe(channel)}-{_safe(chat_id)}.json"

    def _cursor_path(self, channel: str) -> Path:
        return self._root / f"{_safe(channel)}-cursor.json"

    async def load(self, channel: str, chat_id: str) -> ChatState | None:
        path = self._path(channel, chat_id)
        if not path.exists():
            return None
        try:
            return ChatState.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            # Named, because the fix is to look at the file. Silently starting
            # fresh would re-send every reply this chat has ever had.
            raise ChatStateError(f"cannot read chat state at {path}: {err}") from err

    async def save(self, state: ChatState) -> None:
        path = self._path(state.channel, state.chat_id)
        _write_atomic(self._root, path, state.model_dump_json())

    async def chats_of(self, conversation_id: str) -> list[ChatState]:
        # A scan, because there is no index and the directory is one file per
        # chat this process has ever talked to — small, and read on the one
        # path that has nothing better to key on. Only files this class named
        # are chats: the directory outlives layouts, and an `offset.json` from
        # an earlier design once took a whole resume down with a parse error.
        found: list[ChatState] = []
        for path in sorted(self._root.glob("*-*.json")):
            if path.name.endswith("-cursor.json"):
                continue
            try:
                state = ChatState.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # Not one of ours, or damaged: `load` names it the day that
                # chat speaks; a lookup for a *different* conversation must
                # not fail on it.
                continue
            if state.conversation_id == conversation_id:
                found.append(state)
        return found

    async def cursor(self, channel: str) -> str:
        path = self._cursor_path(channel)
        if not path.exists():
            return ""
        try:
            return str(json.loads(path.read_text(encoding="utf-8"))["cursor"])
        except (OSError, ValueError, KeyError, TypeError) as err:
            raise ChatStateError(f"cannot read cursor at {path}: {err}") from err

    async def set_cursor(self, channel: str, value: str) -> None:
        _write_atomic(self._root, self._cursor_path(channel), json.dumps({"cursor": value}))


def _safe(value: str) -> str:
    """A filename component that cannot escape the directory."""
    return _SAFE.sub("_", value)


def _write_atomic(root: Path, path: Path, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    # `replace` rather than a link dance: atomic on POSIX and Windows alike, and
    # a leftover .tmp from an earlier crash must not block a fresh write.
    os.replace(tmp, path)
    _fsync_dir(root)


def _fsync_dir(directory: Path) -> None:
    """Make the rename itself durable, not just the bytes it points at."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
