"""Where each chat's files are kept: an upload's bytes, and the files that are a chat's."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path, PurePosixPath
from typing import Protocol

from harness.files.domain.models import ChatFile, WorkspaceEntry


class ChatFileRepository(Protocol):
    """Each chat's workspace of files, as storage."""

    async def write(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> ChatFile:
        """`chunks` as the file `name` in a new upload folder; on any failure none stays."""
        ...

    def workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, resolved; `ValueError` for an id not one plain name."""
        ...

    def create_workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, made readable by us alone when it is missing."""
        ...

    def file_at(self, chat_id: str, path: str) -> ChatFile | None:
        """The file at absolute `path` when it is one in this chat's workspace or old folder."""
        ...

    def folder_in(self, chat_id: str, path: str) -> Path:
        """The folder `path` names in this chat's workspace, resolved; else `WorkspacePathError`."""
        ...

    def entries_in(self, chat_id: str, folder: Path) -> tuple[WorkspaceEntry, ...]:
        """What `folder` holds; a link leading outside the workspace, or to nothing, left out."""
        ...

    def delete_in(self, chat_id: str, target: PurePosixPath) -> None:
        """Delete the entry `target` names, a link as a link; else `WorkspacePathError`."""
        ...

    def delete_workspace(self, chat_id: str) -> None:
        """Delete this chat's workspace and everything in it; nothing when it is missing."""
        ...
