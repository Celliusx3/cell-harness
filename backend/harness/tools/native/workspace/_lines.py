"""What `workspace_read` hands back: a file's numbered lines, a range, a cap; or a folder's list."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.files import FolderEntries
from harness.files.domain.errors import BadRangeError

MAX_LINES = 2000


@dataclass(frozen=True)
class LineRange:
    """The lines asked for, counting from 1, both ends included; `None` runs to the file's end."""

    start: int
    end: int | None


def numbered(path: Path, text: str, lines: LineRange) -> str:
    """`text`'s lines in `lines` as `<n>\\t<line>`, at most `MAX_LINES`, saying where it stopped."""
    every = text.splitlines()
    if not every:
        return f"{path} is empty."
    last = len(every) if lines.end is None else min(lines.end, len(every))
    if lines.start > last:
        raise BadRangeError(
            f"no lines from {lines.start} to {lines.end or 'the end'}; "
            f"{path} has {len(every)} lines"
        )
    stop = min(last, lines.start + MAX_LINES - 1)
    shown = [f"{n}\t{every[n - 1]}" for n in range(lines.start, stop + 1)]
    if stop < last:
        shown.append(f"Stopped at line {stop} of {len(every)} lines.")
    return "\n".join(shown)


def listed(folder: FolderEntries) -> str:
    """`folder`'s entries, one per line as they are ordered, each folder's name ending in /."""
    if not folder.entries:
        return f"The folder {folder.path} is empty."
    return "\n".join(
        f"{entry.name}/" if entry.kind == "folder" else entry.name for entry in folder.entries
    )
