"""A model's text box on a plain bubble, found again as the lines of letters it closes in."""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from PIL import Image, ImageChops, ImageDraw

from comic.chapter.pages import Box, Colour, Corners, Size
from comic.chapter.plan import padded

GROW_SHARE = 1.5
GROW_MIN = 60
SAME_COLOUR = 40
SEEDS = 7
INSIDE_SHARE = 0.3
REACH = 24
BUBBLE = 255
FILLED = 128
KINDS = 8
MOST_BUBBLE_PIXELS = 250_000


class Point(NamedTuple):
    x: int
    y: int


def dominant_colour(page: Image.Image, box: Box) -> Colour:
    """The commonest of KINDS colours inside `box`: the bubble's, when its text sits on one."""
    colours = page.crop(box.corners()).quantize(colors=KINDS)
    _, index = max(colours.getcolors())
    red, green, blue = colours.getpalette()[3 * index : 3 * index + 3]
    return Colour(red, green, blue)


def _seeds(text: Box) -> list[Point]:
    """Points spread over `text`, the ones nearest its centre first."""
    points = [
        Point(
            text.x + (2 * column + 1) * text.w // (2 * SEEDS),
            text.y + (2 * row + 1) * text.h // (2 * SEEDS),
        )
        for row in range(SEEDS)
        for column in range(SEEDS)
    ]
    cx, cy = text.x + text.w / 2, text.y + text.h / 2
    return sorted(points, key=lambda p: (p.x - cx) ** 2 + (p.y - cy) ** 2)


def _bubble_mask(crop: Image.Image, ground: Colour) -> Image.Image:
    """BUBBLE where a pixel is within SAME_COLOUR of `ground` on every channel, else 0."""
    r, g, b = ImageChops.difference(crop, Image.new("RGB", crop.size, ground)).split()
    farthest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return farthest.point(lambda v: 0 if v > SAME_COLOUR else BUBBLE)


def _flooded_inside(bubble_mask: Image.Image, text: Box) -> Image.Image | None:
    """The bubble's inside as FILLED, flooded from a bubble-coloured point in `text`, or None."""
    least = INSIDE_SHARE * text.w * text.h
    for point in _seeds(text):
        if bubble_mask.getpixel(point) != BUBBLE:
            continue
        flooded = bubble_mask.copy()
        ImageDraw.floodfill(flooded, point, FILLED, thresh=0)
        if flooded.histogram()[FILLED] >= least:
            return flooded
    return None


def _letter_mask(flooded: Image.Image) -> Image.Image:
    """What the flooded inside closes in: every other pixel not joined to the crop's edge."""
    rest = flooded.point(lambda v: 0 if v == FILLED else BUBBLE)
    framed = Image.new("L", (rest.width + 2, rest.height + 2), BUBBLE)
    framed.paste(rest, (1, 1))
    ImageDraw.floodfill(framed, (0, 0), 0, thresh=0)
    return framed.crop((1, 1, rest.width + 1, rest.height + 1))


def _letter_rows(letters: Image.Image) -> list[range]:
    """The runs of rows that hold letters, top to bottom, each as the range of its rows."""
    inked = [
        letters.crop((0, y, letters.width, y + 1)).getbbox() is not None
        for y in range(letters.height)
    ]
    runs: list[range] = []
    for y, has in enumerate(inked):
        if has and (not runs or runs[-1].stop < y):
            runs.append(range(y, y + 1))
        elif has:
            runs[-1] = range(runs[-1].start, y + 1)
    return runs


def _line_boxes(letters: Image.Image) -> list[Box]:
    """Each run of letter rows as the box its letters fill."""
    boxes = []
    for rows in _letter_rows(letters):
        found = letters.crop((0, rows.start, letters.width, rows.stop)).getbbox()
        if found is not None:
            boxes.append(Box(found[0], rows.start, found[2] - found[0], rows.stop - rows.start))
    return boxes


def _in_crop_of(box: Box, area: Box) -> Box:
    """`box` in the pixels of the crop of `area`."""
    return box._replace(x=box.x - area.x, y=box.y - area.y)


def _is_closed(flooded: Image.Image) -> bool:
    """The flooded inside stops short of every edge of the area it was flooded in."""
    width, height = flooded.size
    edges = (
        (0, 0, width, 1),
        (0, height - 1, width, height),
        (0, 0, 1, height),
        (width - 1, 0, width, height),
    )
    return not any(flooded.crop(edge).histogram()[FILLED] for edge in edges)


def _is_centre_inside(flooded: Image.Image, letters: Image.Image, box: Box) -> bool:
    """The centre of `box` is on the flooded inside or on a mark it closes in."""
    x, y = box.x + box.w // 2, box.y + box.h // 2
    if not (0 <= x < flooded.width and 0 <= y < flooded.height):
        return False
    return flooded.getpixel((x, y)) == FILLED or letters.getpixel((x, y)) == BUBBLE


def _is_whole_bubble(flooded: Image.Image, letters: Image.Image, others: list[Box]) -> bool:
    """The inside is closed, at most MOST_BUBBLE_PIXELS, and holds no centre of `others`."""
    return (
        _is_closed(flooded)
        and flooded.histogram()[FILLED] <= MOST_BUBBLE_PIXELS
        and not any(_is_centre_inside(flooded, letters, other) for other in others)
    )


def _lines_reached(letters: Image.Image, text: Box) -> list[Box]:
    """The lines within REACH of `text`'s columns that overlap its rows."""
    left, right = max(0, text.x - REACH), min(letters.width, text.x + text.w + REACH)
    reached = _line_boxes(letters.crop((left, 0, right, letters.height)))
    overlapping = [b for b in reached if b.y < text.y + text.h and b.y + b.h > text.y]
    return [b._replace(x=b.x + left) for b in overlapping]


def letter_lines(page: Image.Image, text: Box, ground: Colour, others: list[Box]) -> list[Box]:
    """Every line of the closed bubble `text` alone points into, else the lines `text` overlaps."""
    grow = max(GROW_MIN, round(GROW_SHARE * text.h))
    area = padded(text, grow, Size(*page.size))
    bubble_mask = _bubble_mask(page.crop(area.corners()), ground)
    local = _in_crop_of(text, area)
    flooded = _flooded_inside(bubble_mask, local)
    if flooded is None:
        return []
    letters = _letter_mask(flooded)
    whole = _is_whole_bubble(flooded, letters, [_in_crop_of(other, area) for other in others])
    found = _line_boxes(letters) if whole else _lines_reached(letters, local)
    return [b._replace(x=b.x + area.x, y=b.y + area.y) for b in found]


def _is_plain(bubble_mask: Image.Image, strip: Corners) -> bool:
    """Every pixel of `strip` is the bubble's colour, and the strip lies inside `bubble_mask`."""
    inside = (
        strip.left >= 0
        and strip.top >= 0
        and strip.right <= bubble_mask.width
        and strip.bottom <= bubble_mask.height
    )
    return inside and bubble_mask.crop(strip).getextrema()[0] == BUBBLE


def _plain_reach(bubble_mask: Image.Image, strip_at: Callable[[int], Corners], pad: int) -> int:
    """How far, up to `pad`, the one-pixel strips `strip_at(1)`, `strip_at(2)`… stay plain."""
    return next(
        (step - 1 for step in range(1, pad + 1) if not _is_plain(bubble_mask, strip_at(step))), pad
    )


def padded_inside(page: Image.Image, line: Box, pad: int, ground: Colour) -> Box:
    """`line` grown by up to `pad` on each side, each side stopping before a mark or an outline."""
    area = padded(line, pad, Size(*page.size))
    bubble_mask = _bubble_mask(page.crop(area.corners()), ground)
    x0, y0 = line.x - area.x, line.y - area.y
    x1, y1 = x0 + line.w, y0 + line.h
    left = _plain_reach(bubble_mask, lambda s: Corners(x0 - s, y0, x0 - s + 1, y1), pad)
    right = _plain_reach(bubble_mask, lambda s: Corners(x1 + s - 1, y0, x1 + s, y1), pad)
    top = _plain_reach(
        bubble_mask, lambda s: Corners(x0 - left, y0 - s, x1 + right, y0 - s + 1), pad
    )
    bottom = _plain_reach(
        bubble_mask, lambda s: Corners(x0 - left, y1 + s - 1, x1 + right, y1 + s), pad
    )
    return Box(line.x - left, line.y - top, line.w + left + right, line.h + top + bottom)


def box_around(boxes: list[Box]) -> Box:
    """The one box that holds every box in `boxes`."""
    x0, y0 = min(b.x for b in boxes), min(b.y for b in boxes)
    x1, y1 = max(b.x + b.w for b in boxes), max(b.y + b.h for b in boxes)
    return Box(x0, y0, x1 - x0, y1 - y0)
