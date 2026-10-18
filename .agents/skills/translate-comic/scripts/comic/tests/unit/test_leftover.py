"""A light region of an erased page still closing in rows or columns of letters is flagged."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from comic.chapter.pages import PAGES, Box, Page, Size
from comic.chapter.parts import part_areas
from comic.chapter.work import WorkFolder
from comic.lettering.leftover import left_over_at, text_areas
from comic.models import LeftOver
from comic.steps.write import left_over

BUBBLE = Box(100, 60, 400, 280)
TALL_PAGE = Page(page="001.png", size=Size(1000, 6000), parts=part_areas(Size(1000, 6000)))


def rows(top: int, lines: int, letters: int) -> list[Box]:
    """`lines` rows of `letters` letter-sized marks."""
    return [
        Box(180 + 20 * n, top + 40 * line, 12, 16) for line in range(lines) for n in range(letters)
    ]


def columns(left: int, lines: int, letters: int) -> list[Box]:
    """`lines` columns of `letters` letter-sized marks, read top to bottom."""
    return [
        Box(left + 30 * line, 130 + 24 * n, 16, 16) for line in range(lines) for n in range(letters)
    ]


def drawn(page: Image.Image, marks: list[Box]) -> NDArray[np.uint8]:
    """`page` with each of `marks` filled black, as an RGB array."""
    pen = ImageDraw.Draw(page)
    for mark in marks:
        pen.rectangle((mark.x, mark.y, mark.x + mark.w - 1, mark.y + mark.h - 1), fill="black")
    return np.asarray(page)


def bubble_page(marks: list[Box]) -> NDArray[np.uint8]:
    """A grey page holding a white bubble outlined in black, with `marks` drawn in it."""
    page = Image.new("RGB", (600, 400), (90, 90, 90))
    ImageDraw.Draw(page).ellipse(BUBBLE.corners(), fill="white", outline="black", width=3)
    return drawn(page, marks)


def is_around(area: Box, marks: list[Box]) -> bool:
    return (
        all(
            area.x <= m.x
            and area.y <= m.y
            and m.x + m.w <= area.x + area.w
            and m.y + m.h <= area.y + area.h
            for m in marks
        )
        and BUBBLE.x <= area.x
        and area.x + area.w <= BUBBLE.x + BUBBLE.w
    )


def test_a_bubble_still_holding_rows_of_letters_is_flagged() -> None:
    marks = rows(160, lines=2, letters=8)

    [area] = text_areas(bubble_page(marks))

    assert is_around(area, marks)


def test_a_bubble_still_holding_columns_of_letters_is_flagged() -> None:
    marks = columns(260, lines=3, letters=6)

    [area] = text_areas(bubble_page(marks))

    assert is_around(area, marks)


def test_a_short_line_of_three_letters_is_flagged() -> None:
    marks = rows(160, lines=1, letters=3)

    [area] = text_areas(bubble_page(marks))

    assert is_around(area, marks)


def test_thin_hatching_the_size_of_letters_is_not_text() -> None:
    page = Image.new("RGB", (600, 400), (90, 90, 90))
    pen = ImageDraw.Draw(page)
    pen.ellipse(BUBBLE.corners(), fill="white", outline="black", width=3)
    for line in range(2):
        for n in range(8):
            x, y = 180 + 30 * n, 140 + 50 * line
            pen.line((x, y + 28, x + 28, y), fill="black", width=1)

    assert text_areas(np.asarray(page)) == []


def test_an_erased_bubble_is_not_flagged() -> None:
    assert text_areas(bubble_page([])) == []


def test_a_region_of_a_few_long_strokes_is_not_flagged() -> None:
    strokes = [Box(200, top, 200, 4) for top in (150, 190, 230)]

    assert text_areas(bubble_page(strokes)) == []


def test_letters_among_more_than_three_long_strokes_are_artwork() -> None:
    strokes = [Box(200, top, 200, 4) for top in (120, 240, 260, 280)]

    assert text_areas(bubble_page(rows(160, lines=2, letters=8) + strokes)) == []


def test_letters_on_a_light_region_touching_the_page_edge_are_not_flagged() -> None:
    page = Image.new("RGB", (600, 400), (90, 90, 90))
    ImageDraw.Draw(page).rectangle((100, 0, 500, 300), fill="white")

    assert text_areas(drawn(page, rows(160, lines=2, letters=8))) == []


def test_an_area_is_named_in_the_first_part_that_holds_it_whole() -> None:
    assert TALL_PAGE.parts[:2] == [Box(0, 0, 1000, 2500), Box(0, 2000, 1000, 2500)]

    assert left_over_at(TALL_PAGE, Box(100, 2100, 200, 300)) == LeftOver(
        part=1, box_2d=(840, 100, 960, 300)
    )
    assert left_over_at(TALL_PAGE, Box(100, 2400, 200, 200)) == LeftOver(
        part=2, box_2d=(160, 100, 240, 300)
    )


def test_an_area_no_part_holds_whole_is_named_in_the_part_sharing_most_clamped() -> None:
    assert left_over_at(TALL_PAGE, Box(0, 1900, 100, 800)) == LeftOver(
        part=2, box_2d=(0, 0, 280, 100)
    )


def test_a_write_names_what_is_left_on_the_clean_page_by_part(tmp_path: Path) -> None:
    size = Size(600, 1800)
    page = Image.new("RGB", size, (90, 90, 90))
    ImageDraw.Draw(page).ellipse((100, 1260, 500, 1540), fill="white", outline="black", width=3)
    clean = drawn(page, [m._replace(y=m.y + 1200) for m in rows(160, lines=2, letters=8)])
    work = WorkFolder(tmp_path / "ch1-english")
    work.clean_folder().mkdir(parents=True)
    Image.fromarray(clean).save(work.clean_png("001.png"))
    work.pages_json().write_bytes(
        PAGES.dump_json([Page(page="001.png", size=size, parts=part_areas(size))])
    )

    [found] = left_over(work, "001.png")

    assert found.part == 2
    ymin, xmin, ymax, xmax = found.box_2d
    assert 0 < ymin < ymax < 1000
    assert 0 < xmin < xmax < 1000
