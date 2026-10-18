"""Where a page is cut into the parts a model is shown, as areas in page pixels."""

from __future__ import annotations

from comic.chapter.pages import Box, Size

TALL = 2.5
OVERLAP = 500


def part_areas(size: Size) -> list[Box]:
    """A tall page as overlapping areas top to bottom, the last ending at its foot; else whole."""
    height = round(TALL * size.width)
    if size.height <= height:
        return [Box(0, 0, size.width, size.height)]
    overlap = min(OVERLAP, height // 2)
    tops = range(0, size.height - overlap, height - overlap)
    return [Box(0, top, size.width, min(height, size.height - top)) for top in tops]
