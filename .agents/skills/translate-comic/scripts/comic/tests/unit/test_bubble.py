"""The English goes in a box grown inside its bubble, kept a margin clear of the outline."""

from __future__ import annotations

from PIL import Image, ImageDraw

from comic.chapter.pages import Box, Colour
from comic.chapter.plan import Plan, shared_area
from comic.lettering.bubble import letter_box, placements
from comic.lettering.clean import Erasure, Ground

PAGE = (1414, 2000)
PX = 71


def plan_at(text: Box) -> Plan:
    return Plan(english="Good luck", text=text, erase=text, fill=text, px=PX, smallest=28)


def page_with(shape: str, corners: tuple[int, int, int, int]) -> Image.Image:
    page = Image.new("RGB", PAGE, (90, 90, 90))
    pen = ImageDraw.Draw(page)
    draw = pen.ellipse if shape == "ellipse" else pen.rectangle
    draw(corners, fill="white", outline="black", width=3)
    return page


def test_a_narrow_tall_bubble_keeps_most_of_its_width_for_the_english() -> None:
    page = page_with("ellipse", (580, 1300, 680, 1520))

    letter = letter_box(page, plan_at(Box(605, 1365, 50, 116)), [])

    assert letter.w >= 50


def test_a_wide_caption_keeps_a_margin_of_a_third_of_the_font_size() -> None:
    page = page_with("rectangle", (300, 300, 700, 600))

    letter = letter_box(page, plan_at(Box(400, 400, 200, 100)), [])

    assert letter.x >= 300 + 3 + round(0.3 * PX) - 1
    assert letter.x + letter.w <= 700 - 3 - round(0.3 * PX) + 1


def test_two_lines_in_one_bubble_each_keep_their_letters_off_the_other() -> None:
    page = page_with("rectangle", (300, 300, 700, 600))
    upper, lower = plan_at(Box(400, 330, 200, 60)), plan_at(Box(400, 420, 200, 60))
    white = Ground(Colour(255, 255, 255), "#000000")

    first, second = placements(
        page, [Erasure(upper, white, (upper.erase,)), Erasure(lower, white, (lower.erase,))]
    )

    assert (shared_area(first.letter, lower.text), shared_area(second.letter, upper.text)) == (0, 0)
