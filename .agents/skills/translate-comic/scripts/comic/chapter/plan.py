"""Each item of a page turned into where its text is on the page, what to clear and its sizes."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from comic import ComicError
from comic.chapter.pages import THOUSAND, Box, Item, Page, Size

SMALLEST_PX = 12
SMALLEST_SHARE = 0.02
START_SHARE = 0.05
PAD = 8
AROUND = 0.5
SAME_BUBBLE = 0.5


@dataclass(frozen=True)
class Plan:
    """One item ready to letter: where its text is on the page, what to clear, the sizes to try."""

    english: str
    text: Box
    erase: Box
    fill: Box
    px: int
    smallest: int


def padded(box: Box, pad: int, size: Size) -> Box:
    """`box` grown by `pad` on every side, kept on the page."""
    x0, y0 = max(0, box.x - pad), max(0, box.y - pad)
    x1, y1 = min(size.width, box.x + box.w + pad), min(size.height, box.y + box.h + pad)
    return Box(x0, y0, x1 - x0, y1 - y0)


def text_box(page: Page, item: Item) -> Box:
    """Where the item's text is in page pixels; refused unless its part is one of the page's."""
    if not 1 <= item.part <= len(page.parts):
        raise ComicError(
            f"{page.page}: the item {item.english!r} names part {item.part}, "
            f"but the page has parts 1 to {len(page.parts)}"
        )
    x, y, w, h = page.parts[item.part - 1]
    ymin, xmin, ymax, xmax = item.box_2d
    return Box(
        round(x + xmin / THOUSAND * w),
        round(y + ymin / THOUSAND * h),
        round((xmax - xmin) / THOUSAND * w),
        round((ymax - ymin) / THOUSAND * h),
    )


def shared_area(a: Box, b: Box) -> int:
    """How many pixels `a` and `b` both cover."""
    across = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    down = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    return max(0, across) * max(0, down)


def refuse_repeats(page: Page, items: list[Item], texts: list[Box]) -> None:
    """Refused when two items' text boxes are mostly one box: one bubble sent twice."""
    for (a, box_a), (b, box_b) in combinations(zip(items, texts, strict=True), 2):
        if shared_area(box_a, box_b) > SAME_BUBBLE * min(box_a.w * box_a.h, box_b.w * box_b.h):
            raise ComicError(
                f"{page.page}: {a.english!r} (part {a.part}) and {b.english!r} (part {b.part}) "
                "are the same bubble; send that bubble once, from the part that shows all of it"
            )


def retexted(plan: Plan, text: Box, size: Size) -> Plan:
    """`plan` with its text box moved to `text`, and what to clear and fill moved with it."""
    return Plan(
        english=plan.english,
        text=text,
        erase=padded(text, PAD, size),
        fill=padded(text, round(AROUND * plan.px), size),
        px=plan.px,
        smallest=plan.smallest,
    )


def plans_of(page: Page, items: list[Item]) -> list[Plan]:
    """Each item of a page as a plan, in order; refused on a missing part or a repeated bubble."""
    texts = [text_box(page, item) for item in items]
    refuse_repeats(page, items, texts)
    smallest = max(SMALLEST_PX, round(SMALLEST_SHARE * page.size.width))
    px = max(smallest, round(START_SHARE * page.size.width))
    return [
        Plan(
            english=item.english,
            text=text,
            erase=padded(text, PAD, page.size),
            fill=padded(text, round(AROUND * px), page.size),
            px=px,
            smallest=smallest,
        )
        for item, text in zip(items, texts, strict=True)
    ]
