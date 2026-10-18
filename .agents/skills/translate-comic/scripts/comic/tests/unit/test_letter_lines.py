"""A model's text box on a plain bubble, found again as the lines of letters it closes in."""

from __future__ import annotations

from PIL import Image, ImageDraw

from comic.chapter.pages import Box, Colour
from comic.lettering.letter_lines import box_around, letter_lines

WHITE = Colour(255, 255, 255)
LETTERS = Box(70, 50, 57, 20)
SECOND = Box(70, 76, 57, 14)


def bubble_page(*, two_lines: bool = False) -> Image.Image:
    """A white page with an outlined bubble around black letters, and its neighbour."""
    page = Image.new("RGB", (300, 140), "white")
    pen = ImageDraw.Draw(page)
    pen.ellipse((40, 15, 160, 110), outline="black", width=3)
    rows = [LETTERS, SECOND] if two_lines else [LETTERS]
    for row in rows:
        for x in range(row.x, row.x + row.w, 12):
            pen.rectangle((x, row.y, x + 8, row.y + row.h - 1), fill="black")
    pen.ellipse((165, 20, 285, 100), outline="black", width=3)
    pen.rectangle((195, 50, 255, 69), fill="black")
    return page


def test_a_box_that_cuts_the_letters_finds_the_whole_line() -> None:
    low = Box(LETTERS.x, LETTERS.y + 10, LETTERS.w, LETTERS.h)

    assert letter_lines(bubble_page(), low, WHITE, []) == [LETTERS]


def test_two_lines_are_two_boxes() -> None:
    both = Box(LETTERS.x, LETTERS.y, LETTERS.w, SECOND.y + SECOND.h - LETTERS.y)

    assert letter_lines(bubble_page(two_lines=True), both, WHITE, []) == [LETTERS, SECOND]


def test_the_neighbouring_bubble_and_the_outline_stay_out() -> None:
    box = Box(LETTERS.x - 5, LETTERS.y - 5, 70, 30)

    found = box_around(letter_lines(bubble_page(), box, WHITE, []))

    assert found.x >= 40
    assert found.x + found.w <= 160


def test_a_box_whose_corners_leave_a_big_round_bubble_still_finds_its_letters() -> None:
    page = Image.new("RGB", (1200, 1200), "white")
    pen = ImageDraw.Draw(page)
    pen.ellipse((100, 150, 500, 450), outline="black", width=3)
    for y in range(240, 360, 30):
        for x in range(190, 410, 22):
            pen.rectangle((x, y, x + 15, y + 19), fill="black")
    box = Box(130, 190, 340, 220)

    found = box_around(letter_lines(page, box, WHITE, []))

    assert found.x >= 180
    assert found.y >= 230
    assert found.x + found.w <= 420
    assert found.y + found.h <= 370


def test_a_box_with_no_letters_around_it_finds_none() -> None:
    assert letter_lines(bubble_page(), Box(10, 115, 30, 20), WHITE, []) == []
