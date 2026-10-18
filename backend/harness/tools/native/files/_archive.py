"""Unpack a .zip or .cbz into numbered files beside it, or pack files into a new one."""

from __future__ import annotations

import re
import shutil
import stat
import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import IO

ARCHIVE_SUFFIXES = (".cbz", ".zip")
MAC_METADATA_FOLDER = "__MACOSX"
HIDDEN_PREFIX = "."
UNPACKED_SUFFIX = "-files"
PARTIAL_SUFFIX = ".partial"
MIN_NUMBER_WIDTH = 3
COPY_CHUNK_BYTES = 1024 * 1024
REGULAR_FILE_MODES = (0, stat.S_IFREG)
DIGIT_RUNS = re.compile(r"(\d+)")
UNREADABLE_ZIP_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    NotImplementedError,
    RuntimeError,
)


class ArchiveError(ValueError):
    """An archive call that cannot be done as a whole."""


def natural_key(name: str) -> tuple[str | int, ...]:
    """`2.png` before `10.png`: each run of digits compares as a number."""
    parts = DIGIT_RUNS.split(name.lower())
    return tuple(int(part) if index % 2 else part for index, part in enumerate(parts))


def padded_number(position: int, count: int) -> str:
    """`position` zero-padded to at least three digits, and to as many as `count` has."""
    return f"{position:0{max(MIN_NUMBER_WIDTH, len(str(count)))}d}"


def files_in_order(folder: Path) -> tuple[Path, ...]:
    """The files directly in `folder`, in natural order."""
    files = (path for path in folder.iterdir() if path.is_file())
    return tuple(sorted(files, key=lambda path: natural_key(path.name)))


def should_unpack(entry: zipfile.ZipInfo) -> bool:
    """A regular file, outside `__MACOSX/`, whose own name does not start with a dot."""
    path = PurePosixPath(entry.filename)
    return (
        not entry.is_dir()
        and stat.S_IFMT(entry.external_attr >> 16) in REGULAR_FILE_MODES
        and MAC_METADATA_FOLDER not in path.parts
        and not path.name.startswith(HIDDEN_PREFIX)
    )


def extract_archive(archive: Path, max_bytes: int) -> tuple[Path, ...]:
    """The files of `archive`, numbered in `<stem>-files/` beside it, unpacked once."""
    folder = archive.with_name(f"{archive.stem}{UNPACKED_SUFFIX}")
    if not folder.is_dir():
        try:
            with zipfile.ZipFile(archive) as zipped:
                unpack_entries(zipped, folder, max_bytes)
        except UNREADABLE_ZIP_ERRORS as err:
            raise ArchiveError(f"{archive} is not a readable .zip or .cbz: {err}") from err
    return files_in_order(folder)


def unpack_entries(zipped: zipfile.ZipFile, folder: Path, max_bytes: int) -> None:
    """Each file entry written as `NNN<ext>`, then the partial folder renamed to `folder`."""
    entries = sorted(
        (entry for entry in zipped.infolist() if should_unpack(entry)),
        key=lambda entry: natural_key(entry.filename),
    )
    if not entries:
        raise ArchiveError(f"{zipped.filename} holds no files")
    declared = sum(entry.file_size for entry in entries)
    if declared > max_bytes:
        raise ArchiveError(
            f"{zipped.filename} would unpack to {declared} bytes, more than the {max_bytes} "
            "bytes allowed; nothing was written"
        )
    partial = folder.with_name(f"{folder.name}{PARTIAL_SUFFIX}")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir()
    try:
        write_numbered_entries(zipped, entries, partial, max_bytes)
        partial.rename(folder)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise


def write_numbered_entries(
    zipped: zipfile.ZipFile, entries: Sequence[zipfile.ZipInfo], folder: Path, max_bytes: int
) -> None:
    """Each entry's bytes at `folder/NNN<ext>`, by position, never by the entry's own path."""
    budget = max_bytes
    for position, entry in enumerate(entries, start=1):
        suffix = PurePosixPath(entry.filename).suffix.lower()
        target = folder / f"{padded_number(position, len(entries))}{suffix}"
        with zipped.open(entry) as reader, target.open("xb") as writer:
            budget -= copy_within(reader, writer, budget)


def copy_within(reader: IO[bytes], writer: IO[bytes], budget: int) -> int:
    """The bytes copied from `reader` to `writer`; `ArchiveError` before a chunk past `budget`."""
    copied = 0
    while chunk := reader.read(COPY_CHUNK_BYTES):
        copied += len(chunk)
        if copied > budget:
            raise ArchiveError(
                "the archive's files unpack to more bytes than it declared, past the limit; "
                "nothing was written"
            )
        writer.write(chunk)
    return copied


def pack_archive(files: Sequence[Path], name: str) -> Path:
    """A new archive `name` beside the first file, holding each as `NNN-<its name>`, in order."""
    if Path(name).name != name:
        raise ArchiveError(f"{name} has a folder in it; give a plain file name")
    if Path(name).suffix not in ARCHIVE_SUFFIXES:
        raise ArchiveError(f"{name} does not end in .cbz or .zip")
    destination = files[0].with_name(name)
    if destination.exists():
        raise ArchiveError(f"{destination} already exists; choose another name")
    partial = destination.with_name(f"{name}{PARTIAL_SUFFIX}")
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED) as packing:
            for position, file in enumerate(files, start=1):
                packing.write(file, f"{padded_number(position, len(files))}-{file.name}")
        partial.rename(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return destination
