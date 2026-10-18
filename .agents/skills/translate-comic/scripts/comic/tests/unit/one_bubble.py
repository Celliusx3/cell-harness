"""A 600x800 page of one outlined bubble holding two lines of letters, and its one item."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from comic.chapter.pages import Item

LETTER_ROWS = (420, 452)
BOX_2D = (519, 358, 594, 642)


def bubble_items(english: str) -> list[Item]:
    """The page's one item: its two lines of letters, to be lettered `english`."""
    return [Item(part=1, box_2d=BOX_2D, original="ABCDEFGHIJ", english=english)]


def saved_bubble_page(path: Path) -> Path:
    """The page saved at `path`: white, one bubble outlined in black, black letters inside."""
    page = Image.new("RGB", (600, 800), "white")
    pen = ImageDraw.Draw(page)
    pen.ellipse((100, 300, 500, 600), outline="black", width=3)
    for top in LETTER_ROWS:
        for x in range(220, 380, 16):
            pen.rectangle((x, top, x + 9, top + 17), fill="black")
    page.save(path)
    return path
