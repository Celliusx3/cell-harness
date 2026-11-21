"""Workspace files on disk as the tools read and change them: text only, inside the given roots."""

from __future__ import annotations

import asyncio
import os
import stat
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from harness.files.domain.errors import (
    NotAFileError,
    NotAFolderError,
    NotTextError,
    OutsideWorkspaceError,
    WorkspaceDiskError,
    WorkspaceFileError,
    WorkspaceFileExistsError,
    WorkspaceFileTooLargeError,
)
from harness.files.domain.models import WorkspaceEntry
from harness.files.domain.search import TextFile
from harness.files.domain.text_edit import MAX_TEXT_BYTES
from harness.files.repository.disk_file_repository import FOLDER_MODE, workspace_entry

TEMP_SUFFIX = ".tmp"
NEW_FILE_MODE = 0o666
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


class Located(NamedTuple):
    """A path resolved inside a workspace, and that workspace's folder."""

    path: Path
    root: Path


class WorkspaceTextRepository:
    """Text files in the workspaces on disk, each edit to one file applied after the last."""

    def __init__(self) -> None:
        self._locks: dict[Path, asyncio.Lock] = {}

    def inside(self, roots: Sequence[Path], path: str) -> Located:
        """`path` resolved, links too, in the first of `roots` it lands in; refused in none."""
        candidate = Path(path)
        if not candidate.is_absolute():
            raise OutsideWorkspaceError(path)
        try:
            resolved = candidate.resolve()
            homes = [root.resolve() for root in roots]
        except (OSError, ValueError, RuntimeError) as err:
            raise OutsideWorkspaceError(path) from err
        home = next((home for home in homes if resolved.is_relative_to(home)), None)
        if home is None:
            raise OutsideWorkspaceError(path)
        return Located(path=resolved, root=home)

    def is_folder(self, target: Path) -> bool:
        """Whether `target` is a folder."""
        return target.is_dir()

    def is_file(self, target: Path) -> bool:
        """Whether `target` is a file."""
        return target.is_file()

    def read_text(self, target: Path) -> str:
        """The UTF-8 text of the file at `target`, never through a link; refused past the cap."""
        with on_disk(target):
            data = _read_capped(target)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as err:
            raise NotTextError(str(target)) from err

    def entries(self, folder: Located) -> tuple[WorkspaceEntry, ...]:
        """What `folder` holds; a link leading outside its workspace, or to nothing, left out."""
        with on_disk(folder.path), os.scandir(folder.path) as found:
            listed = (workspace_entry(item, folder.root) for item in found)
            return tuple(entry for entry in listed if entry is not None)

    def text_files(self, folder: Located) -> Iterator[TextFile]:
        """Each readable UTF-8 text file under `folder` within the cap, links left out, in order."""
        if not folder.path.is_dir():
            raise NotAFolderError(str(folder.path))
        with on_disk(folder.path):
            paths = sorted(p for p in folder.path.rglob("*") if p.is_file() and not p.is_symlink())
        files = (_text_file_or_none(self, path) for path in paths)
        return (file for file in files if file is not None)

    def create(self, place: Located, text: str) -> None:
        """`text` as a new file at `place`, its folders made; refused when something is there."""
        target = place.path
        if os.path.lexists(target):
            raise WorkspaceFileExistsError(str(target))
        with on_disk(target):
            target.parent.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)
            parent = target.parent.resolve()
        if not parent.is_relative_to(place.root):
            raise OutsideWorkspaceError(str(target))
        _write_new(parent / target.name, text)

    async def rewrite(self, target: Path, change: Callable[[str], str]) -> None:
        """The file at `target` rewritten as `change` of its text, one rewrite of it at a time."""
        async with self._locks.setdefault(target, asyncio.Lock()):
            await asyncio.to_thread(self._rewrite_now, target, change)

    def _rewrite_now(self, target: Path, change: Callable[[str], str]) -> None:
        text = change(self.read_text(target))
        with on_disk(target):
            _replace_atomically(target, text)


@contextmanager
def on_disk(path: Path) -> Iterator[None]:
    """An `OSError` from the disk raised as a typed refusal about `path`."""
    try:
        yield
    except FileNotFoundError as err:
        raise NotAFileError(str(path)) from err
    except OSError as err:
        raise WorkspaceDiskError(str(path), err.strerror or type(err).__name__) from err


def _read_capped(target: Path) -> bytes:
    """The bytes of the regular file at `target`, opened without following a link."""
    handle = os.open(target, READ_FLAGS)
    try:
        _ensure_small_file(target, os.fstat(handle))
        with os.fdopen(handle, "rb", closefd=False) as file:
            data = file.read(MAX_TEXT_BYTES + 1)
    finally:
        os.close(handle)
    if len(data) > MAX_TEXT_BYTES:
        raise WorkspaceFileTooLargeError(str(target), MAX_TEXT_BYTES)
    return data


def _ensure_small_file(target: Path, info: os.stat_result) -> None:
    """Refused unless `info` is of a regular file within `MAX_TEXT_BYTES`."""
    if not stat.S_ISREG(info.st_mode):
        raise NotAFileError(str(target))
    if info.st_size > MAX_TEXT_BYTES:
        raise WorkspaceFileTooLargeError(str(target), MAX_TEXT_BYTES)


def _write_new(target: Path, text: str) -> None:
    """`text` as a file at `target` that was not there, never through a link."""
    with on_disk(target):
        try:
            handle = os.open(target, CREATE_FLAGS, NEW_FILE_MODE)
        except FileExistsError as err:
            raise WorkspaceFileExistsError(str(target)) from err
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
            file.write(text)


def _text_file_or_none(repository: WorkspaceTextRepository, target: Path) -> TextFile | None:
    """The file at `target` as a `TextFile`; `None` when it is not readable text within the cap."""
    try:
        return TextFile(path=str(target), text=repository.read_text(target))
    except WorkspaceFileError:
        return None


def _replace_atomically(target: Path, text: str) -> None:
    """`text` written beside `target` with its mode, then moved over it, so no reader sees half."""
    mode = stat.S_IMODE(os.stat(target).st_mode)
    handle, temp = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=TEMP_SUFFIX
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
            os.fchmod(file.fileno(), mode)
            file.write(text)
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
