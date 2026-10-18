"""Light regions of an erased page still closing in rows or columns of letters, by pixels alone."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from comic.chapter.pages import THOUSAND, Box, Page, Size
from comic.chapter.plan import shared_area
from comic.models import LeftOver

LIGHT = 215
CHANNELS = 3
SMALLEST_REGION = 1_500
LARGEST_REGION = 600_000
GLYPH_SHORTEST = 8
GLYPH_TALLEST = 90
GLYPH_WIDEST = 140
LEAST_GAP = 8
GAP_SHARE = 0.6
LEAST_GLYPHS = 3
LEAST_RUN = 3
LEAST_INK = 0.2
MOST_STRETCH = 4.0
MOST_STROKES = 3
LEAST_EXTENT = 0.55


def box_of(found: tuple[slice, slice]) -> Box:
    """The box a `find_objects` entry covers."""
    rows, columns = found
    return Box(columns.start, rows.start, columns.stop - columns.start, rows.stop - rows.start)


class Mark(NamedTuple):
    """One dark shape a light region closes in: its box and how many pixels it inks."""

    box: Box
    ink: int


def is_glyph(mark: Mark) -> bool:
    """A compact mark the size of one letter."""
    box = mark.box
    return (
        GLYPH_SHORTEST <= box.h <= GLYPH_TALLEST
        and box.w <= GLYPH_WIDEST
        and mark.ink >= LEAST_INK * box.w * box.h
        and max(box.h / box.w, box.w / box.h) <= MOST_STRETCH
    )


def is_stroke(mark: Mark) -> bool:
    """A mark too tall or too wide to be one letter."""
    return mark.box.h > GLYPH_TALLEST or mark.box.w > GLYPH_WIDEST


def largest_group(centres: Sequence[float], gap: float) -> int:
    """The most centres in one group, sorted and split where neighbours are over `gap` apart."""
    ordered = np.sort(np.asarray(centres, dtype=np.float64))
    bounds = np.concatenate(([0], np.flatnonzero(np.diff(ordered) > gap) + 1, [ordered.size]))
    return int(np.diff(bounds).max())


def longest_run(glyphs: Sequence[Box]) -> int:
    """The most of `glyphs` that share one row or one column."""
    gap = max(LEAST_GAP, GAP_SHARE * float(np.median([g.h for g in glyphs])))
    rows = largest_group([g.y + g.h / 2 for g in glyphs], gap)
    columns = largest_group([g.x + g.w / 2 for g in glyphs], gap)
    return max(rows, columns)


def is_text(marks: Sequence[Mark], extent: float) -> bool:
    """Enough letters in a row or a column, few long strokes, in a region that fills its box."""
    glyphs = [mark.box for mark in marks if is_glyph(mark)]
    strokes = sum(1 for mark in marks if is_stroke(mark))
    return (
        len(glyphs) >= LEAST_GLYPHS
        and strokes <= MOST_STROKES
        and extent >= LEAST_EXTENT
        and longest_run(glyphs) >= LEAST_RUN
    )


def has_text(region: NDArray[np.bool_]) -> bool:
    """`region`, cropped to its box, is bubble-sized and the marks it closes in read as text."""
    filled = ndimage.binary_fill_holes(region)
    area = int(np.count_nonzero(filled))
    if not SMALLEST_REGION <= area <= LARGEST_REGION:
        return False
    holes, _ = ndimage.label(filled & ~region)
    inks = np.bincount(holes.ravel())
    marks = [
        Mark(box_of(found), int(inks[index]))
        for index, found in enumerate(ndimage.find_objects(holes), start=1)
    ]
    return is_text(marks, area / region.size)


def is_candidate(region: Box, pixels: int, page: Size) -> bool:
    """A region clear of the page's edge whose box and pixels leave room for a bubble."""
    is_clear = (
        region.x > 0
        and region.y > 0
        and region.x + region.w < page.width
        and region.y + region.h < page.height
    )
    return is_clear and region.w * region.h >= SMALLEST_REGION and pixels <= LARGEST_REGION


def text_areas(image: NDArray[np.uint8]) -> list[Box]:
    """Each light region of an RGB `image` that still holds text, as its box in pixels."""
    light = image.sum(axis=2, dtype=np.uint16) >= CHANNELS * LIGHT
    labels, _ = ndimage.label(light)
    pixels = np.bincount(labels.ravel())
    page = Size(width=light.shape[1], height=light.shape[0])
    regions = [box_of(found) for found in ndimage.find_objects(labels)]
    return [
        region
        for index, region in enumerate(regions, start=1)
        if is_candidate(region, int(pixels[index]), page)
        and has_text(
            labels[region.y : region.y + region.h, region.x : region.x + region.w] == index
        )
    ]


def is_within(area: Box, part: Box) -> bool:
    """`area` lies whole inside `part`."""
    return (
        part.x <= area.x
        and part.y <= area.y
        and area.x + area.w <= part.x + part.w
        and area.y + area.h <= part.y + part.h
    )


def thousandths(offset: int, length: int) -> int:
    """`offset` as thousandths of `length`, kept within 0 to 1000."""
    return min(THOUSAND, max(0, round(offset / length * THOUSAND)))


def left_over_at(page: Page, area: Box) -> LeftOver:
    """`area` as an item names it: in the first part holding it whole, else the one sharing most."""
    parts = page.parts
    holding = [n for n, part in enumerate(parts) if is_within(area, part)]
    index = (
        holding[0] if holding else max(range(len(parts)), key=lambda n: shared_area(area, parts[n]))
    )
    part = parts[index]
    return LeftOver(
        part=index + 1,
        box_2d=(
            thousandths(area.y - part.y, part.h),
            thousandths(area.x - part.x, part.w),
            thousandths(area.y + area.h - part.y, part.h),
            thousandths(area.x + area.w - part.x, part.w),
        ),
    )
