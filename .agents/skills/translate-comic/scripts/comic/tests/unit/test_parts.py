"""A tall page is cut into overlapping parts top to bottom; any other page is one part."""

from __future__ import annotations

from comic.chapter.pages import Box, Size
from comic.chapter.parts import OVERLAP, TALL, part_areas


def test_a_page_no_taller_than_the_limit_is_one_part_the_whole_page() -> None:
    assert part_areas(Size(1080, round(TALL * 1080))) == [Box(0, 0, 1080, 2700)]


def test_a_tall_page_is_cut_into_parts_that_each_start_overlap_before_the_last_ends() -> None:
    parts = part_areas(Size(1080, 15990))

    assert [part.y for part in parts] == [0, 2200, 4400, 6600, 8800, 11000, 13200, 15400]
    assert all(part.x == 0 and part.w == 1080 and part.h <= 2700 for part in parts)
    assert all(b.y == a.y + a.h - OVERLAP for a, b in zip(parts, parts[1:], strict=False))


def test_the_last_part_ends_at_the_foot_of_the_page() -> None:
    last = part_areas(Size(1080, 15990))[-1]

    assert last == Box(0, 15400, 1080, 590)
    assert last.y + last.h == 15990


def test_a_narrow_tall_page_overlaps_by_half_a_part() -> None:
    assert part_areas(Size(100, 600)) == [
        Box(0, 0, 100, 250),
        Box(0, 125, 100, 250),
        Box(0, 250, 100, 250),
        Box(0, 375, 100, 225),
    ]
