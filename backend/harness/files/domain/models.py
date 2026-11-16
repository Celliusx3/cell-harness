"""A file a chat holds, as the log records it, and one folder of a chat's workspace."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePath
from typing import Literal

from pydantic import BaseModel, ConfigDict

ROOT_PATH = ""


class ChatFile(BaseModel):
    """A file in a chat's workspace: where it is on disk, its name, type and size."""

    model_config = ConfigDict(frozen=True)

    path: str
    name: str
    media_type: str
    size: int


class WorkspaceEntry(BaseModel):
    """One entry of a workspace folder: its name, whether it is a folder, and its size."""

    model_config = ConfigDict(frozen=True)

    name: str
    kind: Literal["file", "folder"]
    size: int


class WorkspaceListing(BaseModel):
    """One folder of a chat's workspace, by its path relative to the workspace, "" for the root."""

    model_config = ConfigDict(frozen=True)

    path: str
    workspace: str
    entries: tuple[WorkspaceEntry, ...]


class WorkspacePathError(LookupError):
    """A workspace path that leaves the workspace, is missing, or is not a folder."""


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
