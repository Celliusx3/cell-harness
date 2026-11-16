"""Where each chat's files are kept: an upload's bytes, and the paths that are a chat's."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from harness.files.domain.models import WorkspaceEntry

FOLDER_MODE = 0o700
NOT_A_NAME = frozenset({"", ".", ".."})


def is_plain_name(text: str) -> bool:
    """Whether `text` is one entry's name: not empty, `.`, `..`, a path, or holding a NUL."""
    return text not in NOT_A_NAME and Path(text).name == text and "\x00" not in text


class ChatFileRepository(Protocol):
    """Each chat's workspace of files, as storage."""

    async def write(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> Path:
        """`chunks` as the file `name` in a new upload folder; on any failure none stays."""
        ...

    def workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, resolved; `ValueError` for an id not one plain name."""
        ...

    def path_in(self, chat_id: str, path: str) -> Path | None:
        """`path` resolved, when absolute and a file in this chat's workspace or old folder."""
        ...

    def folder_in(self, chat_id: str, path: str) -> Path:
        """The folder `path` names in this chat's workspace, resolved; else `WorkspacePathError`."""
        ...

    def entries_in(self, chat_id: str, folder: Path) -> tuple[WorkspaceEntry, ...]:
        """What `folder` holds; a link leading outside the workspace, or to nothing, left out."""
        ...

    def delete_workspace(self, chat_id: str) -> None:
        """Delete this chat's workspace and everything in it; nothing when it is missing."""
        ...

    def create_root(self) -> None:
        """The folder every chat's files live under, readable by us alone, made if missing."""
        ...
