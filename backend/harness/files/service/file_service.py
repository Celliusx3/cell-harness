"""A chat's files as callers use them: an upload saved by the rules, the file a path names."""

from __future__ import annotations

import asyncio
import mimetypes
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path

from harness.files.domain.models import (
    ChatFile,
    WorkspaceEvent,
    WorkspaceListing,
    deletion_target,
    relative_path,
    sorted_entries,
)
from harness.files.repository.file_repository import (
    FOLDER_MODE,
    ChatFileRepository,
    is_plain_name,
)
from harness.files.service.workspace_watch import workspace_events

UNKNOWN_MEDIA_TYPE = "application/octet-stream"


class FileTooLargeError(Exception):
    """An upload went past the limit, and nothing of it was kept."""

    def __init__(self, name: str, max_bytes: int) -> None:
        super().__init__(
            f"{name!r} is larger than {max_bytes} bytes, the most one upload may be; "
            "nothing was saved"
        )


class UnsafeFileNameError(ValueError):
    """A file name with nothing left to save under once its folders are stripped."""


def safe_name(name: str) -> str:
    """The last part of `name`; `UnsafeFileNameError` if it is empty, `.`, `..` or holds a NUL."""
    base = Path(name).name
    if not is_plain_name(base):
        raise UnsafeFileNameError(f"{name!r} does not name a file")
    return base


def media_type_of(name: str) -> str:
    """The type `name`'s extension implies, or `application/octet-stream`."""
    guessed, _ = mimetypes.guess_type(name)
    return guessed or UNKNOWN_MEDIA_TYPE


async def _within_limit(
    chunks: AsyncIterator[bytes], name: str, max_bytes: int
) -> AsyncIterator[bytes]:
    """`chunks` as they come; `FileTooLargeError` before one would take them past `max_bytes`."""
    written = 0
    async for chunk in chunks:
        written += len(chunk)
        if written > max_bytes:
            raise FileTooLargeError(name, max_bytes)
        yield chunk


def _chat_file(path: Path) -> ChatFile:
    """The file on disk at `path`, as the log records it."""
    return ChatFile(
        path=str(path),
        name=path.name,
        media_type=media_type_of(path.name),
        size=path.stat().st_size,
    )


class ChatFileService:
    """Each chat's files for the routes and tools: an upload saved, or the file a path names."""

    def __init__(self, repository: ChatFileRepository, *, max_bytes: int) -> None:
        self._repository = repository
        self._max_bytes = max_bytes

    def workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, made readable by us alone when it is missing."""
        workspace = self._repository.workspace(chat_id)
        self._repository.create_root()
        workspace.parent.mkdir(mode=FOLDER_MODE, exist_ok=True)
        workspace.mkdir(mode=FOLDER_MODE, exist_ok=True)
        return workspace

    def delete_workspace(self, chat_id: str) -> None:
        """Delete this chat's workspace and everything in it; nothing when it is missing."""
        self._repository.delete_workspace(chat_id)

    def listing(self, chat_id: str, path: str) -> WorkspaceListing:
        """The folder `path` names in this chat's workspace, folders first; refused outside it."""
        workspace = self._repository.workspace(chat_id)
        if path == "" and not workspace.exists():
            return WorkspaceListing(path="", workspace=str(workspace), entries=())
        folder = self._repository.folder_in(chat_id, path)
        return WorkspaceListing(
            path=relative_path(workspace, folder),
            workspace=str(workspace),
            entries=sorted_entries(self._repository.entries_in(chat_id, folder)),
        )

    def delete_path(self, chat_id: str, path: str) -> None:
        """Delete the file, folder or link `path` names in this chat's workspace; else refused."""
        self._repository.delete_in(chat_id, deletion_target(path))

    def changes(self, chat_id: str) -> AsyncGenerator[WorkspaceEvent]:
        """This chat's workspace watched, made first when missing, until the caller closes it."""
        return workspace_events(self.workspace(chat_id), asyncio.Event())

    def file_at(self, chat_id: str, path: str) -> ChatFile | None:
        """The file at absolute `path` when it is one in this chat's workspace or old folder."""
        found = self._repository.path_in(chat_id, path)
        return _chat_file(found) if found is not None else None

    async def save(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> ChatFile:
        """An upload kept under its name's last part; past the limit or unnamed, nothing is kept."""
        base = safe_name(name)
        limited = _within_limit(chunks, base, self._max_bytes)
        return _chat_file(await self._repository.write(chat_id, base, limited))
