"""English that runs onto a bubble's outline is named as a spill; English well inside is not."""

from __future__ import annotations

from PIL import Image, ImageDraw

from comic.chapter.pages import Box
from comic.chapter.plan import Plan
from comic.lettering.spills import spilling_lines

PAGE = (300, 200)
BUBBLE = (60, 50, 240, 150)
ERASE = Box(100, 80, 100, 40)
WELL_INSIDE = (130, 90, 170, 110)
ACROSS_THE_OUTLINE = (50, 95, 75, 105)


def plan() -> Plan:
    return Plan(english="Hi!", text=ERASE, erase=ERASE, fill=ERASE, px=20, smallest=12)


def clean_page() -> Image.Image:
    """A white page with one closed bubble outlined in black."""
    page = Image.new("RGB", PAGE, "white")
    ImageDraw.Draw(page).ellipse(BUBBLE, outline="black", width=3)
    return page


def inked(corners: tuple[int, int, int, int]) -> Image.Image:
    """The clean page with black ink filling `corners`."""
    page = clean_page()
    ImageDraw.Draw(page).rectangle(corners, fill="black")
    return page


def test_english_well_inside_its_bubble_does_not_spill() -> None:
    assert spilling_lines(clean_page(), inked(WELL_INSIDE), [plan()]) == []


def test_english_drawn_across_the_bubble_outline_spills() -> None:
    assert spilling_lines(clean_page(), inked(ACROSS_THE_OUTLINE), [plan()]) == ["Hi!"]
