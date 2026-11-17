"""A chat's files as callers use them: an upload saved by the rules, the file a path names."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from pathlib import Path

from harness.files.domain.errors import FileTooLargeError
from harness.files.domain.models import (
    ChatFile,
    WorkspaceEvent,
    WorkspaceListing,
    deletion_target,
    relative_path,
    sorted_entries,
)
from harness.files.domain.names import plain_name_of
from harness.files.repository.file_repository import ChatFileRepository
from harness.files.service.workspace_watch import workspace_events


async def _capped_chunks(
    chunks: AsyncIterator[bytes], name: str, max_bytes: int
) -> AsyncIterator[bytes]:
    """`chunks` as they come; `FileTooLargeError` before one would take them past `max_bytes`."""
    written = 0
    async for chunk in chunks:
        written += len(chunk)
        if written > max_bytes:
            raise FileTooLargeError(name, max_bytes)
        yield chunk


class ChatFileService:
    """Each chat's files for the routes and tools: an upload saved, or the file a path names."""

    def __init__(self, repository: ChatFileRepository, *, max_bytes: int) -> None:
        self._repository = repository
        self._max_bytes = max_bytes

    def workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, made readable by us alone when it is missing."""
        return self._repository.create_workspace(chat_id)

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
        return self._repository.file_at(chat_id, path)

    async def save(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> ChatFile:
        """An upload kept under its name's last part; past the limit or unnamed, nothing is kept."""
        base = plain_name_of(name)
        return await self._repository.write(
            chat_id, base, _capped_chunks(chunks, base, self._max_bytes)
        )
