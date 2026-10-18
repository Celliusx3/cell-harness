"""A text layer too wide for its letter box shrinks a step at a time until it fits."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from comic.chapter.pages import Box
from comic.chapter.plan import Plan
from comic.connection import connected
from comic.document import opened
from comic.lettering.text_layers import Placement, create_layers, fitted_layers, is_fitting
from comic.tests.unit.fake_photocraft import TOKEN, FakePhotoCraft

LETTER_BOX = Box(100, 100, 100, 100)


def test_a_line_too_wide_at_its_planned_size_shrinks_until_it_fits(
    tmp_path: Path, photocraft: FakePhotoCraft
) -> None:
    page = tmp_path / "001.png"
    Image.new("RGB", (400, 400), "white").save(page)
    plan = Plan("Hello", LETTER_BOX, LETTER_BOX, LETTER_BOX, px=40, smallest=10)

    with connected(photocraft.addr, TOKEN) as session, opened(session, page) as document:
        created = create_layers(document, [Placement(plan, LETTER_BOX, "#000000")])
        (fitted,) = fitted_layers(document, created, 1.0)

    assert (fitted.px, is_fitting(fitted)) == (31, True)
