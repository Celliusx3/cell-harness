"""A file a chat holds, as the log records it, one folder of a chat's workspace, and its changes."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path, PurePath, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict

from harness.files.domain.errors import WorkspacePathError

ROOT_PATH = ""
NOT_AN_ENTRY_NAME = frozenset({"", ".."})


class ChatFile(BaseModel):
    """A file in a chat's workspace: where it is on disk, its name, type and size."""

    model_config = ConfigDict(frozen=True)

    path: str
    name: str
    media_type: str
    size: int


class WorkspaceEntry(BaseModel):
    """One entry of a workspace folder: its name, kind, size and change time."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: Literal["file", "folder"]
    size: int
    modified: datetime


class WorkspaceListing(BaseModel):
    """One folder of a chat's workspace, by its path relative to the workspace, "" for the root."""

    model_config = ConfigDict(frozen=True)

    path: str
    workspace: str
    entries: tuple[WorkspaceEntry, ...]


class FileText(BaseModel):
    """A workspace text file as a tool read it: its resolved path, and its text."""

    model_config = ConfigDict(frozen=True)

    path: Path
    text: str


class FolderEntries(BaseModel):
    """A workspace folder as a tool read it: its resolved path, and what it holds, folders first."""

    model_config = ConfigDict(frozen=True)

    path: Path
    entries: tuple[WorkspaceEntry, ...]


class WorkspaceWatching(BaseModel):
    """The workspace is watched from now on: a change after this one is told."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    type: Literal["workspace/watching"] = "workspace/watching"


class WorkspaceChanged(BaseModel):
    """Something in this folder of the workspace changed, by its relative path, "" for the root."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    type: Literal["workspace/changed"] = "workspace/changed"
    folder: str


WorkspaceEvent = WorkspaceWatching | WorkspaceChanged


def sorted_entries(entries: Iterable[WorkspaceEntry]) -> tuple[WorkspaceEntry, ...]:
    """`entries` folders first, then files, each group by name regardless of case."""
    return tuple(
        sorted(
            entries, key=lambda entry: (entry.kind != "folder", entry.name.casefold(), entry.name)
        )
    )


def relative_path(workspace: PurePath, folder: PurePath) -> str:
    """`folder` as a path relative to `workspace`, "" for the workspace itself."""
    relative = folder.relative_to(workspace)
    return ROOT_PATH if relative == PurePath() else relative.as_posix()


def deletion_target(path: str) -> PurePosixPath:
    """`path` as the entry a delete names, relative and not the root; else `WorkspacePathError`."""
    target = PurePosixPath(path)
    if target.is_absolute() or target.name in NOT_AN_ENTRY_NAME:
        raise WorkspacePathError(f"{path!r} does not name an entry inside the workspace")
    return target


def changed_folders(workspace: PurePath, changed: Iterable[PurePath]) -> tuple[str, ...]:
    """Each folder holding a `changed` path inside `workspace`, relative, once, children first."""
    folders = {
        relative_path(workspace, path.parent)
        for path in changed
        if path.parent.is_relative_to(workspace)
    }
    return tuple(sorted(folders, reverse=True))
