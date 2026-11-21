"""Workspace text files as the tools use them, and the version each model history last read."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

from harness.files.domain.errors import WorkspaceFileTooLargeError
from harness.files.domain.memory_view import MEMORY_PATH
from harness.files.domain.models import FileText, FolderEntries, sorted_entries
from harness.files.domain.search import Match, matches
from harness.files.domain.text_edit import (
    MAX_TEXT_BYTES,
    TextEdit,
    edited,
    unchanged_since_read,
    version_of,
)
from harness.files.repository.workspace_text_repository import WorkspaceTextRepository

ReadKey = tuple[str, Path]


class WorkspaceTextService:
    """Read, write, edit and search text inside the workspaces a call reaches, read before edit."""

    def __init__(self, repository: WorkspaceTextRepository) -> None:
        self._repository = repository
        self._read_versions: dict[ReadKey, str] = {}

    async def read(
        self, roots: Sequence[Path], path: str, history_id: str
    ) -> FileText | FolderEntries:
        """The folder at `path`, folders first, or its file's text, remembered as read."""
        read = await asyncio.to_thread(self._read_now, roots, path)
        if isinstance(read, FileText):
            self._read_versions[(history_id, read.path)] = version_of(read.text)
        return read

    def _read_now(self, roots: Sequence[Path], path: str) -> FileText | FolderEntries:
        place = self._repository.inside(roots, path)
        if self._repository.is_folder(place.path):
            entries = sorted_entries(self._repository.entries(place))
            return FolderEntries(path=place.path, entries=entries)
        return FileText(path=place.path, text=self._repository.read_text(place.path))

    async def write(self, roots: Sequence[Path], path: str, text: str, history_id: str) -> Path:
        """`text` as a new file at `path`, counted as read; refused when there or too large."""
        place = self._repository.inside(roots, path)
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise WorkspaceFileTooLargeError(str(place.path), MAX_TEXT_BYTES)
        await asyncio.to_thread(self._repository.create, place, text)
        self._read_versions[(history_id, place.path)] = version_of(text)
        return place.path

    async def edit(
        self, roots: Sequence[Path], path: str, change: TextEdit, history_id: str
    ) -> Path:
        """The file at `path` with `change` made, when `history_id` last read it as it is."""
        target = self._repository.inside(roots, path).path
        key = (history_id, target)

        def changed(text: str) -> str:
            current = unchanged_since_read(text, self._read_versions.get(key), path)
            new = edited(current, change.find, change.replace)
            self._read_versions[key] = version_of(new)
            return new

        await self._repository.rewrite(target, changed)
        return target

    async def search(self, roots: Sequence[Path], query: str, folder: str) -> tuple[Match, ...]:
        """The lines of the text files under `folder` that hold `query`, ignoring case, capped."""
        return await asyncio.to_thread(self._search_now, roots, query, folder)

    def _search_now(self, roots: Sequence[Path], query: str, folder: str) -> tuple[Match, ...]:
        place = self._repository.inside(roots, folder)
        return matches(self._repository.text_files(place), query)

    async def memory(self, workspace: Path) -> str | None:
        """The text of `workspace`'s memory file; `None` when it has none."""
        return await asyncio.to_thread(self._memory_now, workspace)

    def _memory_now(self, workspace: Path) -> str | None:
        target = self._repository.inside((workspace,), str(workspace / MEMORY_PATH)).path
        if not self._repository.is_file(target):
            return None
        return self._repository.read_text(target)
