"""The one rule for the paths a command names, and the work folder and page they lead to."""

from __future__ import annotations

from pathlib import Path

from comic import ComicError
from comic.chapter.pages import Page
from comic.chapter.work import WorkFolder


def absolute_path(raw: str) -> Path:
    """`raw` resolved; refused unless it is absolute."""
    path = Path(raw)
    if not path.is_absolute():
        raise ComicError(f"{raw} is not an absolute path")
    return path.resolve()


def work_folder(raw: str) -> WorkFolder:
    """The work folder `raw` names; refused unless `pages` made it."""
    work = WorkFolder(absolute_path(raw))
    if not work.is_unpacked():
        raise ComicError(f"{raw} holds no pages.json; pass the `work` that `pages` printed")
    return work


def page_of(work: WorkFolder, name: str) -> Page:
    """The page called `name` in pages.json; refused when there is none."""
    page = next((page for page in work.pages() if page.page == name), None)
    if page is None:
        raise ComicError(f"{name} is not a page in {work.pages_json()}")
    return page
