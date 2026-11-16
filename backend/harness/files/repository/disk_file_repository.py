"""Each chat's files on disk, uploads under `<workspace>/uploads/<random folder>/`, ours alone."""

from __future__ import annotations

import secrets
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from harness.files.repository.file_repository import FOLDER_MODE, is_plain_name

WORKSPACES = "workspaces"
UPLOADS = "uploads"
TOKEN_BYTES = 16


@dataclass(frozen=True)
class DiskChatFileRepository:
    """Every chat's files, under `<root>/workspaces/<chat id>/` and its old `<root>/<chat id>/`."""

    root: Path

    def folder(self, chat_id: str) -> Path:
        """This chat's folder from before workspaces, resolved; `ValueError` for an unplain id."""
        if not is_plain_name(chat_id):
            raise ValueError(f"{chat_id!r} cannot name a chat's folder")
        return (self.root / chat_id).resolve()

    def workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, resolved; `ValueError` for an id not one plain name."""
        if not is_plain_name(chat_id):
            raise ValueError(f"{chat_id!r} cannot name a chat's workspace")
        return (self.root / WORKSPACES / chat_id).resolve()

    def path_in(self, chat_id: str, path: str) -> Path | None:
        """`path` resolved, when absolute and a file in this chat's workspace or old folder."""
        candidate = Path(path)
        if not candidate.is_absolute():
            return None
        try:
            resolved = candidate.resolve()
            homes = (self.workspace(chat_id), self.folder(chat_id))
            inside = any(resolved.is_relative_to(home) for home in homes) and resolved.is_file()
        except (OSError, ValueError):
            return None
        return resolved if inside else None

    async def write(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> Path:
        """`chunks` as the file `name` in a new upload folder; on any failure none stays."""
        if not is_plain_name(name):
            raise ValueError(f"{name!r} cannot name a file")
        folder = self._create_upload_folder(chat_id)
        target = folder / name
        try:
            with target.open("xb") as handle:
                async for chunk in chunks:
                    handle.write(chunk)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return target

    def delete_workspace(self, chat_id: str) -> None:
        """Delete this chat's workspace and everything in it; nothing when it is missing."""
        workspace = self.workspace(chat_id)
        if workspace.exists():
            shutil.rmtree(workspace)

    def create_root(self) -> None:
        """The folder every chat's files live under, readable by us alone, made if missing."""
        self.root.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)

    def _create_upload_folder(self, chat_id: str) -> Path:
        """A fresh folder in the workspace's `uploads/`, named by a random token, ours alone."""
        self.create_root()
        uploads = self.workspace(chat_id) / UPLOADS
        for folder in (uploads.parent.parent, uploads.parent, uploads):
            folder.mkdir(mode=FOLDER_MODE, exist_ok=True)
        fresh = uploads / secrets.token_urlsafe(TOKEN_BYTES)
        fresh.mkdir(mode=FOLDER_MODE)
        return fresh
