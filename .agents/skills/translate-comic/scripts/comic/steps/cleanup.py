"""cleanup: delete everything in a work folder but the archive the person was sent."""

from __future__ import annotations

import logging
from pathlib import Path

from comic import ComicError
from comic.chapter.work import WorkFolder
from comic.models import CleanupResult
from comic.steps import absolute_path, work_folder

logger = logging.getLogger("comic.cleanup")


def file_to_keep(raw: str, work: WorkFolder) -> Path:
    """The file `raw` names, resolved; refused unless it is a file, not a link, inside `work`."""
    path = absolute_path(raw)
    if not path.is_relative_to(work.root):
        raise ComicError(f"{raw} is not inside the work folder {work.root}")
    if not path.exists():
        raise ComicError(f"{raw} does not exist")
    if not path.is_file() or Path(raw).is_symlink():
        raise ComicError(f"{raw} is not a file; pass the archive's own path")
    return path


def removable_files(root: Path, keep: Path) -> list[Path]:
    """Every file and link under `root` but `keep`; a link is listed, never followed."""
    return [
        folder / name
        for folder, _, names in root.walk(follow_symlinks=False)
        for name in names
        if folder / name != keep
    ]


def removable_folders(root: Path, keep: Path) -> list[Path]:
    """Every folder under `root` that does not hold `keep`, the deepest first."""
    return [
        folder / name
        for folder, names, _ in root.walk(top_down=False, follow_symlinks=False)
        for name in names
        if not keep.is_relative_to(folder / name)
    ]


def empty_all_but(work: WorkFolder, keep: Path) -> CleanupResult:
    """`work` with only `keep` left in it, and how many files and bytes went."""
    files = removable_files(work.root, keep)
    folders = removable_folders(work.root, keep)
    freed = sum(path.lstat().st_size for path in files)
    for path in files:
        path.unlink()
    for path in folders:
        path.rmdir()
    logger.info("%s: kept %s, removed %d files, %d bytes", work.root, keep.name, len(files), freed)
    return CleanupResult(kept=str(keep), removed_files=len(files), freed_bytes=freed)


def clean_up_work_folder(work: str, keep: str) -> CleanupResult:
    """The work folder emptied of all but `keep`; refused unless `keep` is a file inside it."""
    folder = work_folder(work)
    return empty_all_but(folder, file_to_keep(keep, folder))
