"""A box clears its whole bubble only when the bubble is closed, small enough, and its own."""

from __future__ import annotations

import math

import pytest
from PIL import Image, ImageDraw

from comic.chapter.pages import Box, Corners, Size
from comic.chapter.plan import Plan, padded
from comic.lettering.clean import erasures_of
from comic.lettering.letter_lines import MOST_BUBBLE_PIXELS

PAGE = Size(1400, 1400)
LINE_TOPS = (760, 800, 840)
LINE_HEIGHT = 22
LETTERS_FROM, LETTERS_TO = 500, 900
ROUGH_BOX = Box(560, 675, 300, 250)
REACHED_LINES = Box(536, 760, 348, 102)
SMALL_BUBBLE = Corners(440, 600, 960, 1000)
BIG_BUBBLE = Corners(360, 490, 1040, 1110)
GUTTER_TOP, GUTTER_BOTTOM = 700, 920
OTHER_BUBBLE = Corners(980, 320, 1220, 560)
OTHER_LETTERS = Box(1040, 430, 120, 22)
FAR_BOX = Box(20, 20, 40, 20)


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


def filled(page: Image.Image, box: Box) -> None:
    ImageDraw.Draw(page).rectangle((box.x, box.y, box.x + box.w - 1, box.y + box.h - 1), "black")


def lettered_page(*bubbles: Corners) -> Image.Image:
    """A white page with the three lines of black letters, each of `bubbles` outlined in black."""
    page = Image.new("RGB", PAGE, "white")
    for bubble in bubbles:
        ImageDraw.Draw(page).ellipse(bubble, outline="black", width=3)
    for block in letters():
        filled(page, block)
    return page


def covered(block: Box, areas: tuple[Box, ...]) -> bool:
    return any(
        area.x <= block.x
        and area.y <= block.y
        and block.x + block.w <= area.x + area.w
        and block.y + block.h <= area.y + area.h
        for area in areas
    )


def inside_pixels(bubble: Corners) -> float:
    left, top, right, bottom = bubble
    return math.pi * (right - left) / 2 * (bottom - top) / 2


def test_text_on_a_gutter_keeps_only_the_lines_the_box_reaches() -> None:
    page = lettered_page()
    filled(page, Box(0, 0, PAGE.width, GUTTER_TOP))
    filled(page, Box(0, GUTTER_BOTTOM, PAGE.width, PAGE.height - GUTTER_BOTTOM))

    (erased,) = erasures_of(page, [plan(ROUGH_BOX)])

    assert erased.plan.text == REACHED_LINES


@pytest.mark.parametrize(("bubble", "whole"), [(SMALL_BUBBLE, True), (BIG_BUBBLE, False)])
def test_a_closed_bubble_over_the_cap_keeps_only_the_lines_the_box_reaches(
    bubble: Corners, whole: bool
) -> None:
    assert inside_pixels(SMALL_BUBBLE) < MOST_BUBBLE_PIXELS < inside_pixels(BIG_BUBBLE)

    (erased,) = erasures_of(lettered_page(bubble), [plan(ROUGH_BOX)])

    uncovered = [block for block in letters() if not covered(block, erased.areas)]
    assert (uncovered == []) is whole


def test_another_box_centred_on_a_letter_of_the_bubble_keeps_the_lines_the_box_reaches() -> None:
    on_a_letter = letters()[0]
    page = lettered_page(SMALL_BUBBLE)

    rough, _ = erasures_of(page, [plan(ROUGH_BOX), plan(on_a_letter, "Oi.")])

    assert rough.plan.text == REACHED_LINES


def test_boxes_outside_the_bubble_near_or_far_leave_the_rough_box_its_whole_bubble() -> None:
    page = lettered_page(SMALL_BUBBLE, OTHER_BUBBLE)
    filled(page, OTHER_LETTERS)
    planned = [plan(ROUGH_BOX), plan(OTHER_LETTERS, "Oi."), plan(FAR_BOX, "Far.")]

    rough, _, _ = erasures_of(page, planned)

    assert all(covered(block, rough.areas) for block in letters())
