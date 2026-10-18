"""The band around an erase box decides its fill, colour or content-aware, and the text's ink."""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from comic import ComicError
from comic.chapter.pages import Box, Colour
from comic.chapter.plan import Plan
from comic.document import BatchStep, StepResult
from comic.lettering.clean import Erasure, Ground, erase_steps, ground, missed_erasures

ERASE = Box(30, 30, 40, 20)


def plan(erase: Box) -> Plan:
    return Plan(english="Hi", text=erase, erase=erase, fill=erase, px=12, smallest=12)


def bubble(colour: Colour, letters: Colour) -> Image.Image:
    """A plain page in `colour`, with a block of `letters` inside the erase box."""
    page = Image.new("RGB", (100, 80), colour)
    ImageDraw.Draw(page).rectangle((35, 35, 60, 44), fill=letters)
    return page


def test_a_white_bubble_is_filled_white_and_lettered_black() -> None:
    page = bubble(Colour(255, 255, 255), Colour(0, 0, 0))

    assert ground(page, plan(ERASE)) == Ground(Colour(255, 255, 255), "#000000")


def test_a_dark_plain_box_is_filled_its_colour_and_lettered_white() -> None:
    page = bubble(Colour(30, 30, 60), Colour(255, 255, 255))

    assert ground(page, plan(ERASE)) == Ground(Colour(30, 30, 60), "#ffffff")


def test_paper_grain_under_the_spread_still_counts_as_plain() -> None:
    page = bubble(Colour(250, 250, 250), Colour(0, 0, 0))
    for x in range(0, 100, 2):
        ImageDraw.Draw(page).line((x, 0, x, 79), fill=(240, 240, 240))

    assert ground(page, plan(ERASE)) == Ground(Colour(250, 250, 250), "#000000")


def test_a_bubble_outline_through_the_band_still_counts_as_plain() -> None:
    page = bubble(Colour(255, 255, 255), Colour(0, 0, 0))
    ImageDraw.Draw(page).line((73, 0, 73, 79), fill=(0, 0, 0), width=2)

    assert ground(page, plan(ERASE)) == Ground(Colour(255, 255, 255), "#000000")


def test_a_box_on_artwork_is_left_to_content_aware_fill() -> None:
    page = bubble(Colour(200, 200, 200), Colour(0, 0, 0))
    for x in range(0, 100, 4):
        ImageDraw.Draw(page).line((x, 0, x + 1, 79), fill=(20, 20, 20))

    found = ground(page, plan(ERASE))

    assert found.colour is None
    assert found.ink == "#000000"


def test_the_band_is_clipped_to_the_page_at_its_edge() -> None:
    page = bubble(Colour(255, 255, 255), Colour(0, 0, 0))

    assert ground(page, plan(Box(0, 0, 70, 50))) == Ground(Colour(255, 255, 255), "#000000")


def test_a_box_over_the_whole_page_is_refused() -> None:
    page = Image.new("RGB", (100, 80), (255, 255, 255))

    with pytest.raises(ComicError, match="'Hi' covers the whole page"):
        ground(page, plan(Box(0, 0, 100, 80)))


def test_each_erasure_selects_all_its_areas_then_fills_once() -> None:
    lines = (Box(30, 30, 40, 8), Box(32, 42, 36, 8))
    white = Erasure(plan(ERASE), Ground(Colour(255, 250, 240), "#000000"), lines)
    art = Erasure(plan(Box(1, 2, 3, 4)), Ground(None, "#ffffff"), (Box(1, 2, 3, 4),))

    assert erase_steps([white, art]) == [
        BatchStep(
            command="select.rect",
            params={"x": 30, "y": 30, "width": 40, "height": 8, "mode": "replace"},
        ),
        BatchStep(
            command="select.rect",
            params={"x": 32, "y": 42, "width": 36, "height": 8, "mode": "add"},
        ),
        BatchStep(command="edit.fill", params={"contents": "color", "color": "#fffaf0"}),
        BatchStep(
            command="select.rect",
            params={"x": 1, "y": 2, "width": 3, "height": 4, "mode": "replace"},
        ),
        BatchStep(command="edit.fill", params={"contents": "contentAware"}),
        BatchStep(command="select.deselect", params={}),
    ]


def test_a_box_photocraft_would_not_fill_is_named_with_its_reason() -> None:
    lines = (ERASE, ERASE)
    white = Erasure(plan(ERASE), Ground(Colour(255, 255, 255), "#000000"), lines)
    art = Erasure(Plan("Oi", ERASE, ERASE, ERASE, 12, 12), Ground(None, "#000000"), (ERASE,))
    results = [
        StepResult(ok=True),
        StepResult(ok=True),
        StepResult(ok=True),
        StepResult(ok=True),
        StepResult(ok=False, error="Content-Aware fill needs a selection"),
        StepResult(ok=False, error="no selection"),
    ]

    assert missed_erasures([white, art], results) == ["'Oi' (Content-Aware fill needs a selection)"]
