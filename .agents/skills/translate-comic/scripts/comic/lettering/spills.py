"""Finds English that spills onto the artwork or near a bubble's edge."""

from __future__ import annotations

from PIL import Image, ImageChops, ImageFilter

from comic.chapter.pages import Box, Corners, Size
from comic.chapter.plan import Plan

INK_DIFFERENCE = 20
OTHER_COLOUR_DIFFERENCE = 35
EDGE_NEAR_PX = 5
CHECKED_AREA_SHARE = 0.5
MOST_SPILLED_PIXELS = 15


def _checked_area(erase: Box, size: Size) -> Corners:
    dx, dy = round(erase.w * CHECKED_AREA_SHARE), round(erase.h * CHECKED_AREA_SHARE)
    return Corners(
        max(0, erase.x - dx),
        max(0, erase.y - dy),
        min(size.width, erase.x + erase.w + dx),
        min(size.height, erase.y + erase.h + dy),
    )


def spilled_pixels(clean: Image.Image, english: Image.Image, erase: Box) -> int:
    """English pixels on the artwork or within EDGE_NEAR_PX pixels of the bubble's edge."""
    area = _checked_area(erase, Size(*clean.size))
    before, after = clean.crop(area), english.crop(area)
    ink = (
        ImageChops.difference(before, after)
        .convert("L")
        .point(lambda v: 255 if v > INK_DIFFERENCE else 0)
    )
    seed = clean.getpixel((erase.x + erase.w // 2, erase.y + erase.h // 2))
    r, g, b = ImageChops.difference(before, Image.new("RGB", before.size, seed)).split()
    other = ImageChops.lighter(ImageChops.lighter(r, g), b).point(
        lambda v: 255 if v > OTHER_COLOUR_DIFFERENCE else 0
    )
    near = other.filter(ImageFilter.MaxFilter(2 * EDGE_NEAR_PX + 1))
    return ImageChops.multiply(ink, near).histogram()[255]


def spilling_lines(clean: Image.Image, english: Image.Image, planned: list[Plan]) -> list[str]:
    """The English of each plan with more than MOST_SPILLED_PIXELS pixels spilled."""
    return [
        plan.english
        for plan in planned
        if spilled_pixels(clean, english, plan.erase) > MOST_SPILLED_PIXELS
    ]
