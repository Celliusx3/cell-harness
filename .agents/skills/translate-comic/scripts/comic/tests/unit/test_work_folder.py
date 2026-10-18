"""The work folder names the clean, English and view files of a page after the page."""

from __future__ import annotations

from pathlib import Path

from comic.chapter.work import WorkFolder

ROOT = Path("/chats/c1/ch1-english")


def test_the_clean_english_and_view_files_of_a_page_are_named_after_it() -> None:
    work = WorkFolder(ROOT)

    assert (
        work.clean_png("001.png"),
        work.english_png("001.png"),
        work.page_view("001.png", 1),
        work.english_view("001.png", 1),
    ) == (
        ROOT / "clean" / "001.png",
        ROOT / "english" / "001.png",
        ROOT / "views" / "001-part1.jpg",
        ROOT / "views" / "001-english-part1.jpg",
    )
