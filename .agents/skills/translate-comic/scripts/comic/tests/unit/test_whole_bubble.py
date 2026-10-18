"""A box that points roughly into a closed bubble no other item points into erases all of it."""

from __future__ import annotations

from PIL import Image, ImageDraw

from comic.chapter.pages import Box, Size
from comic.chapter.plan import Plan, padded
from comic.lettering.clean import erasures_of

PAGE = Size(700, 1000)
BUBBLE = (240, 600, 630, 960)
LINE_TOPS = (719, 757, 795, 833)
LINE_HEIGHT = 22
LETTERS_FROM, LETTERS_TO = 288, 596
ROUGH_BOX = Box(414, 763, 196, 177)


def plan(text: Box, english: str = "It seems we won't hold out much longer.") -> Plan:
    return Plan(
        english=english,
        text=text,
        erase=padded(text, 8, PAGE),
        fill=padded(text, 20, PAGE),
        px=35,
        smallest=14,
    )


def letters() -> list[Box]:
    return [
        Box(x, top, 12, LINE_HEIGHT)
        for top in LINE_TOPS
        for x in range(LETTERS_FROM, LETTERS_TO - 12, 18)
    ]


def page_with_bubble() -> Image.Image:
    """A page holding one closed white bubble with four lines of black letters."""
    page = Image.new("RGB", PAGE, "white")
    pen = ImageDraw.Draw(page)
    pen.ellipse(BUBBLE, outline="black", width=3)
    for block in letters():
        pen.rectangle((block.x, block.y, block.x + block.w - 1, block.y + block.h - 1), "black")
    return page


def covered(block: Box, areas: tuple[Box, ...]) -> bool:
    return any(
        area.x <= block.x
        and area.y <= block.y
        and block.x + block.w <= area.x + area.w
        and block.y + block.h <= area.y + area.h
        for area in areas
    )


def test_a_rough_box_in_a_closed_bubble_erases_every_line_of_it() -> None:
    (erased,) = erasures_of(page_with_bubble(), [plan(ROUGH_BOX)])

    assert [block for block in letters() if not covered(block, erased.areas)] == []


def test_two_items_in_one_bubble_keep_only_their_own_lines() -> None:
    upper = Box(LETTERS_FROM, LINE_TOPS[0], LETTERS_TO - LETTERS_FROM, 60)
    lower = Box(LETTERS_FROM, LINE_TOPS[2], LETTERS_TO - LETTERS_FROM, 60)

    first, second = erasures_of(page_with_bubble(), [plan(upper, "One."), plan(lower, "Two.")])

    upper_letters = [block for block in letters() if block.y < LINE_TOPS[2]]
    lower_letters = [block for block in letters() if block.y >= LINE_TOPS[2]]
    assert not any(covered(block, first.areas) for block in lower_letters)
    assert not any(covered(block, second.areas) for block in upper_letters)
