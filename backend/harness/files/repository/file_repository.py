"""Where each chat's files are kept: an upload's bytes, and the paths inside a chat's folder."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

NOT_A_NAME = frozenset({"", ".", ".."})


def is_plain_name(text: str) -> bool:
    """Whether `text` is one entry's name: not empty, `.`, `..`, a path, or holding a NUL."""
    return text not in NOT_A_NAME and Path(text).name == text and "\x00" not in text


class ChatFileRepository(Protocol):
    """Each chat's own folder of files, as storage."""

    async def write(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> Path:
        """`chunks` as the file `name` in a new folder of this chat's; on any failure none stays."""
        ...

    def path_in(self, chat_id: str, path: str) -> Path | None:
        """`path` resolved, when it is absolute and a file in this chat's folder; else `None`."""
        ...
