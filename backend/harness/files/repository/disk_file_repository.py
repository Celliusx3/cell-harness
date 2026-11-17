"""Each chat's files on disk, uploads under `<workspace>/uploads/<random folder>/`, ours alone."""

from __future__ import annotations

import os
import secrets
import shutil
import stat
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from harness.files.domain.errors import WorkspacePathError
from harness.files.domain.models import ChatFile, WorkspaceEntry
from harness.files.domain.names import is_plain_name, media_type_of

FOLDER_MODE = 0o700
WORKSPACES = "workspaces"
UPLOADS = "uploads"
TOKEN_BYTES = 16


@dataclass(frozen=True)
class DiskChatFileRepository:
    """Every chat's files, under `<root>/workspaces/<chat id>/` and its old `<root>/<chat id>/`."""

    root: Path

    def __post_init__(self) -> None:
        self._create_root()

    def workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, resolved; `ValueError` for an id not one plain name."""
        if not is_plain_name(chat_id):
            raise ValueError(f"{chat_id!r} cannot name a chat's workspace")
        return (self.root / WORKSPACES / chat_id).resolve()

    def create_workspace(self, chat_id: str) -> Path:
        """This chat's workspace folder, made readable by us alone when it is missing."""
        workspace = self.workspace(chat_id)
        self._create_root()
        workspace.parent.mkdir(mode=FOLDER_MODE, exist_ok=True)
        workspace.mkdir(mode=FOLDER_MODE, exist_ok=True)
        return workspace

    def file_at(self, chat_id: str, path: str) -> ChatFile | None:
        """The file at absolute `path` when it is one in this chat's workspace or old folder."""
        found = self._path_in(chat_id, path)
        return _chat_file_at(found) if found is not None else None

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

    async def write(self, chat_id: str, name: str, chunks: AsyncIterator[bytes]) -> ChatFile:
        """`chunks` as the file `name` in a new upload folder; on any failure none stays."""
        if not is_plain_name(name):
            raise ValueError(f"{name!r} cannot name a file")
        folder = self._new_upload_folder(chat_id)
        target = folder / name
        try:
            with target.open("xb") as handle:
                async for chunk in chunks:
                    handle.write(chunk)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return _chat_file_at(target)

    def delete_in(self, chat_id: str, target: PurePosixPath) -> None:
        """Delete the entry `target` names, a link as a link; else `WorkspacePathError`."""
        workspace = self.workspace(chat_id)
        parent = (workspace / target.parent).resolve()
        if not parent.is_relative_to(workspace):
            raise WorkspacePathError(f"{str(target)!r} is not inside the workspace")
        _delete_entry(parent / target.name)

    def delete_workspace(self, chat_id: str) -> None:
        """Delete this chat's workspace and everything in it; nothing when it is missing."""
        workspace = self.workspace(chat_id)
        if workspace.exists():
            shutil.rmtree(workspace)

    def _create_root(self) -> None:
        """The folder every chat's files live under, readable by us alone, made if missing."""
        self.root.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)

    def _old_folder(self, chat_id: str) -> Path:
        """This chat's folder from before workspaces, resolved; `ValueError` for an unplain id."""
        if not is_plain_name(chat_id):
            raise ValueError(f"{chat_id!r} cannot name a chat's folder")
        return (self.root / chat_id).resolve()

    def _path_in(self, chat_id: str, path: str) -> Path | None:
        """`path` resolved, when absolute and a file in this chat's workspace or old folder."""
        candidate = Path(path)
        if not candidate.is_absolute():
            return None
        try:
            resolved = candidate.resolve()
            homes = (self.workspace(chat_id), self._old_folder(chat_id))
            inside = any(resolved.is_relative_to(home) for home in homes) and resolved.is_file()
        except (OSError, ValueError):
            return None
        return resolved if inside else None

    def _new_upload_folder(self, chat_id: str) -> Path:
        """A fresh folder in the workspace's `uploads/`, named by a random token, ours alone."""
        uploads = self.create_workspace(chat_id) / UPLOADS
        uploads.mkdir(mode=FOLDER_MODE, exist_ok=True)
        fresh = uploads / secrets.token_urlsafe(TOKEN_BYTES)
        fresh.mkdir(mode=FOLDER_MODE)
        return fresh


def _chat_file_at(path: Path) -> ChatFile:
    """The file on disk at `path`, as the log records it."""
    return ChatFile(
        path=str(path),
        name=path.name,
        media_type=media_type_of(path.name),
        size=path.stat().st_size,
    )


def _entry(item: os.DirEntry[str], workspace: Path) -> WorkspaceEntry | None:
    """`item` as a listed entry; None for a link leading outside `workspace` or to nothing."""
    try:
        if item.is_symlink() and not _is_link_within(Path(item.path), workspace):
            return None
        found = item.stat()
        modified = datetime.fromtimestamp(found.st_mtime, tz=UTC)
        if item.is_dir():
            return WorkspaceEntry(name=item.name, kind="folder", size=0, modified=modified)
        return WorkspaceEntry(name=item.name, kind="file", size=found.st_size, modified=modified)
    except OSError:
        return None


def _delete_entry(entry: Path) -> None:
    """Delete `entry` without following it: a folder with all it holds, else the one entry."""
    try:
        mode = entry.lstat().st_mode
    except FileNotFoundError as err:
        raise WorkspacePathError(f"{entry.name!r} is not in the workspace") from err
    if stat.S_ISDIR(mode):
        shutil.rmtree(entry)
    else:
        entry.unlink()


def _is_link_within(link: Path, workspace: Path) -> bool:
    target = link.resolve()
    return target.is_relative_to(workspace) and target.exists()
