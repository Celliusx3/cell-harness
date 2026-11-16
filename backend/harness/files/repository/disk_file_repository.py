"""Each chat's files on disk, uploads under `<workspace>/uploads/<random folder>/`, ours alone."""

from __future__ import annotations

import os
import secrets
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from harness.files.domain.models import WorkspaceEntry, WorkspacePathError
from harness.files.repository.file_repository import FOLDER_MODE, is_plain_name

WORKSPACES = "workspaces"
UPLOADS = "uploads"
TOKEN_BYTES = 16


@dataclass(frozen=True)
class DiskChatFileRepository:
    """Every chat's files, under `<root>/workspaces/<chat id>/` and its old `<root>/<chat id>/`."""

    root: Path

    def old_folder(self, chat_id: str) -> Path:
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
            homes = (self.workspace(chat_id), self.old_folder(chat_id))
            inside = any(resolved.is_relative_to(home) for home in homes) and resolved.is_file()
        except (OSError, ValueError):
            return None
        return resolved if inside else None

    def folder_in(self, chat_id: str, path: str) -> Path:
        """The folder `path` names in this chat's workspace, resolved; else `WorkspacePathError`."""
        workspace = self.workspace(chat_id)
        if Path(path).is_absolute():
            raise WorkspacePathError(f"{path!r} is not a path inside the workspace")
        try:
            folder = (workspace / path).resolve()
            is_folder = folder.is_relative_to(workspace) and folder.is_dir()
        except (OSError, ValueError):
            is_folder = False
        if not is_folder:
            raise WorkspacePathError(f"{path!r} is not a folder in the workspace")
        return folder

    def entries_in(self, chat_id: str, folder: Path) -> tuple[WorkspaceEntry, ...]:
        """What `folder` holds; a link leading outside the workspace, or to nothing, left out."""
        workspace = self.workspace(chat_id)
        with os.scandir(folder) as found:
            entries = (_entry(item, workspace) for item in found)
            return tuple(entry for entry in entries if entry is not None)

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


def _entry(item: os.DirEntry[str], workspace: Path) -> WorkspaceEntry | None:
    """`item` as a listed entry; None for a link leading outside `workspace` or to nothing."""
    try:
        if item.is_symlink() and not _is_link_within(Path(item.path), workspace):
            return None
        if item.is_dir():
            return WorkspaceEntry(name=item.name, kind="folder", size=0)
        return WorkspaceEntry(name=item.name, kind="file", size=item.stat().st_size)
    except OSError:
        return None


def _is_link_within(link: Path, workspace: Path) -> bool:
    target = link.resolve()
    return target.is_relative_to(workspace) and target.exists()
