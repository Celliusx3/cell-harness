"""Where the English goes: a box grown inside the bubble from its text's centre."""

from __future__ import annotations

from typing import NamedTuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from comic.chapter.pages import Box, Corners
from comic.chapter.plan import Plan
from comic.lettering.clean import Erasure
from comic.lettering.text_layers import Placement

MARK = (255, 0, 255)
SAME_COLOUR = 80
SPECK = 5
STEP = 3.0
INSIDE_SHARE = 0.98
OPEN_REACH = 1.5
MARGIN = 0.3
MOST_MARGIN_SHARE = 0.1


class Room(NamedTuple):
    mask: Image.Image
    left: int
    top: int


class Edges(NamedTuple):
    left: float
    top: float
    right: float
    bottom: float


def _room(page: Image.Image, plan: Plan, others: list[Box]) -> Room:
    """Where English may go near `plan`, as white on black, kept off the edge and off `others`."""
    x, y, w, h = plan.fill
    area = Corners(
        max(0, x - w), max(0, y - h), min(page.width, x + 2 * w), min(page.height, y + 2 * h)
    )
    around = page.crop(area)
    filled = around.copy()
    ImageDraw.floodfill(
        filled, (x + w // 2 - area.left, y + h // 2 - area.top), MARK, thresh=SAME_COLOUR
    )
    mask = ImageChops.difference(filled, around).convert("L").point(lambda v: 255 if v else 0)
    found = mask.getbbox() or (0, 0, 0, 0)
    if found[0] == 0 or found[1] == 0 or found[2] == around.width or found[3] == around.height:
        reach = round(OPEN_REACH * plan.px)
        keep = Image.new("L", mask.size, 0)
        corners = (
            x - reach - area.left,
            y - reach - area.top,
            x + w + reach - area.left,
            y + h + reach - area.top,
        )
        ImageDraw.Draw(keep).rectangle(corners, fill=255)
        mask = ImageChops.multiply(mask, keep)
    mask = mask.filter(ImageFilter.MaxFilter(SPECK)).filter(ImageFilter.MinFilter(SPECK))
    left, top, right, bottom = mask.getbbox() or (0, 0, 0, 0)
    narrowest = min(right - left, bottom - top)
    margin = max(1, min(round(MARGIN * plan.px), round(MOST_MARGIN_SHARE * narrowest)))
    pen = ImageDraw.Draw(mask)
    for other in others:
        pen.rectangle(
            (
                other.x - area.left,
                other.y - area.top,
                other.x + other.w - area.left,
                other.y + other.h - area.top,
            ),
            fill=0,
        )
    return Room(mask.filter(ImageFilter.MinFilter(2 * margin + 1)), area.left, area.top)


def _is_inside(mask: Image.Image, strip: Edges) -> bool:
    x0, y0, x1, y1 = (round(v) for v in strip)
    if x0 < 0 or y0 < 0 or x1 > mask.width or y1 > mask.height or x1 <= x0 or y1 <= y0:
        return False
    part = mask.crop((x0, y0, x1, y1))
    return part.histogram()[255] >= INSIDE_SHARE * part.width * part.height


def _rectangle_grown_from(mask: Image.Image, cx: int, cy: int) -> Edges | None:
    """The rectangle grown from (cx, cy) in the room's proportions until each side meets an edge."""
    if mask.getpixel((cx, cy)) != 255:
        return None
    left, top, right, bottom = mask.getbbox() or (0, 0, 1, 1)
    wide, tall = max(1, right - left), max(1, bottom - top)
    sx, sy = (STEP * wide / tall, STEP) if wide > tall else (STEP, STEP * tall / wide)
    box = Edges(cx - 1.0, cy - 1.0, cx + 1.0, cy + 1.0)
    moved = True
    while moved:
        grown = _grown_once(mask, box, sx, sy)
        moved, box = grown != box, grown
    return box


def _grown_once(mask: Image.Image, box: Edges, sx: float, sy: float) -> Edges:
    """`box` with each side moved out one step where the strip beyond it is inside the room."""
    if _is_inside(mask, Edges(box.left - sx, box.top, box.left, box.bottom)):
        box = box._replace(left=box.left - sx)
    if _is_inside(mask, Edges(box.right, box.top, box.right + sx, box.bottom)):
        box = box._replace(right=box.right + sx)
    if _is_inside(mask, Edges(box.left, box.top - sy, box.right, box.top)):
        box = box._replace(top=box.top - sy)
    if _is_inside(mask, Edges(box.left, box.bottom, box.right, box.bottom + sy)):
        box = box._replace(bottom=box.bottom + sy)
    return box


def letter_box(page: Image.Image, plan: Plan, others: list[Box]) -> Box:
    """A box grown in the bubble from the text's centre, clear of its edge and `others`."""
    room = _room(page, plan, others)
    found = _rectangle_grown_from(
        room.mask,
        plan.text.x + plan.text.w // 2 - room.left,
        plan.text.y + plan.text.h // 2 - room.top,
    )
    if found is None:
        return plan.erase
    return Box(
        round(found.left) + room.left,
        round(found.top) + room.top,
        round(found.right - found.left),
        round(found.bottom - found.top),
    )


def placements(cleaned: Image.Image, erased: list[Erasure]) -> list[Placement]:
    """Where each line goes on the clean page, kept off the other lines, and its ink."""
    return [
        Placement(
            e.plan,
            letter_box(cleaned, e.plan, [q.plan.text for q in erased if q is not e]),
            e.ground.ink,
        )
        for e in erased
    ]
