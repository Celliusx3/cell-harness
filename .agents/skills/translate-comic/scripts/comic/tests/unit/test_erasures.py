"""Before PhotoCraft erases, each box on a plain bubble is tightened to its letters."""

from __future__ import annotations

from PIL import Image, ImageDraw

from comic.chapter.pages import Box, Colour, Size
from comic.chapter.plan import Plan, padded
from comic.lettering.clean import Ground, erasures_of

TWO_LINES = Box(80, 40, 76, 50)


def plan(text: Box) -> Plan:
    size = Size(300, 160)
    return Plan(
        english="Hi",
        text=text,
        erase=padded(text, 8, size),
        fill=padded(text, 20, size),
        px=20,
        smallest=12,
    )


def page_with_bubble() -> Image.Image:
    """A page that is a white bubble holding two lines of black letters."""
    page = Image.new("RGB", (300, 160), "white")
    pen = ImageDraw.Draw(page)
    pen.ellipse((30, 5, 210, 130), outline="black", width=3)
    for top in (TWO_LINES.y, TWO_LINES.y + 30):
        for x in range(TWO_LINES.x, TWO_LINES.x + TWO_LINES.w, 16):
            pen.rectangle((x, top, x + 11, top + 19), fill="black")
    return page


def test_a_box_that_would_grow_into_another_item_is_kept_as_sent() -> None:
    first_line = Box(TWO_LINES.x, TWO_LINES.y, TWO_LINES.w, 20)
    second_line = Box(TWO_LINES.x, TWO_LINES.y + 30, TWO_LINES.w, 20)

    erased = erasures_of(page_with_bubble(), [plan(first_line), plan(second_line)])

    assert [e.plan.text for e in erased] == [first_line, second_line]


def test_a_box_that_cuts_both_lines_erases_each_line_whole() -> None:
    cutting = Box(TWO_LINES.x + 10, TWO_LINES.y + 5, TWO_LINES.w - 20, TWO_LINES.h - 10)

    (erased,) = erasures_of(page_with_bubble(), [plan(cutting)])

    assert erased.plan.text == TWO_LINES
    assert erased.ground.colour == Colour(255, 255, 255)
    assert erased.plan.erase == padded(erased.plan.text, 8, Size(300, 160))
    assert len(erased.areas) == 2
    assert all(area.h < 30 for area in erased.areas)


def test_a_line_the_box_does_not_reach_is_left_alone() -> None:
    second_line = Box(TWO_LINES.x, TWO_LINES.y + 30, TWO_LINES.w, 20)

    (erased,) = erasures_of(page_with_bubble(), [plan(second_line)])

    assert erased.plan.text == second_line
    assert len(erased.areas) == 1


def test_a_small_bubble_on_dark_ground_is_still_filled_with_its_own_colour() -> None:
    page = Image.new("RGB", (300, 160), (90, 100, 90))
    pen = ImageDraw.Draw(page)
    pen.ellipse((100, 50, 200, 110), fill="white", outline="black", width=3)
    for x in range(125, 175, 12):
        pen.rectangle((x, 70, x + 7, 89), fill="black")

    (erased,) = erasures_of(page, [plan(Box(125, 70, 51, 20))])

    assert erased.ground == Ground(Colour(255, 255, 255), "#000000")
    assert len(erased.areas) == 1


def test_a_box_on_artwork_is_filled_as_one_area() -> None:
    page = Image.new("RGB", (300, 160), "white")
    pen = ImageDraw.Draw(page)
    for x in range(0, 300, 4):
        pen.line((x, 0, x + 1, 159), fill=(20, 20, 20))

    (erased,) = erasures_of(page, [plan(TWO_LINES)])

    assert erased.ground.colour is None
    assert erased.areas == (erased.plan.erase,)


def test_a_line_just_above_a_thin_outline_is_filled_short_of_it() -> None:
    page = Image.new("RGB", (300, 160), "white")
    pen = ImageDraw.Draw(page)
    pen.rectangle((30, 5, 210, 130), outline="black", width=2)
    for x in range(80, 156, 16):
        pen.rectangle((x, 108, x + 7, 127), fill="black")

    (erased,) = erasures_of(page, [plan(Box(80, 108, 72, 20))])

    [area] = erased.areas
    assert area.y + area.h <= 129
    assert (area.x, area.y) == (76, 104)
