"""PhotoCraft erases each item's text: on a plain bubble with its colour, on artwork from around."""

from __future__ import annotations

from typing import NamedTuple

from PIL import Image, ImageChops, ImageStat
from pydantic import JsonValue

from comic import ComicError
from comic.chapter.pages import Box, Colour, Size
from comic.chapter.plan import Plan, padded, retexted, shared_area
from comic.chapter.work import WorkFolder
from comic.connection import Session
from comic.document import BatchStep, StepResult, opened
from comic.lettering.letter_lines import box_around, dominant_colour, letter_lines, padded_inside

RING = 6
NEAR_COLOUR = 40
PLAIN_SHARE = 0.85
LIGHT = 128
DARK_INK = "#000000"
LIGHT_INK = "#ffffff"
LINE_PAD = 4


class Ground(NamedTuple):
    """What is under an item's text: its plain colour, or None on artwork, and the ink to use."""

    colour: Colour | None
    ink: str


class Erasure(NamedTuple):
    """One item to erase: its plan, its ground and the areas filled."""

    plan: Plan
    ground: Ground
    areas: tuple[Box, ...]


def hex_of(colour: Colour) -> str:
    return "#{:02x}{:02x}{:02x}".format(*colour)


def ground(page: Image.Image, plan: Plan) -> Ground:
    """The band RING wide around the erase box: plain when mostly one colour, and dark or light."""
    outer = padded(plan.erase, RING, Size(*page.size))
    mask = Image.new("L", (outer.w, outer.h), 255)
    inner = plan.erase._replace(x=plan.erase.x - outer.x, y=plan.erase.y - outer.y)
    mask.paste(0, inner.corners())
    band = ImageStat.Stat(page.crop(outer.corners()), mask)
    if not band.count[0]:
        raise ComicError(
            f"the box of {plan.english!r} covers the whole page; draw it around the text only"
        )
    median = Colour(*band.median)
    is_plain = near_share(page.crop(outer.corners()), mask, median) >= PLAIN_SHARE
    return Ground(median if is_plain else None, ink_on(median))


def ink_on(colour: Colour) -> str:
    """Dark ink on a light colour, light ink on a dark one."""
    luminance = 0.299 * colour.red + 0.587 * colour.green + 0.114 * colour.blue
    return DARK_INK if luminance > LIGHT else LIGHT_INK


def near_share(crop: Image.Image, mask: Image.Image, colour: Colour) -> float:
    """The share of the masked pixels within NEAR_COLOUR of `colour` on every channel."""
    r, g, b = ImageChops.difference(crop, Image.new("RGB", crop.size, colour)).split()
    farthest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    near = farthest.point(lambda v: 0 if v > NEAR_COLOUR else 255)
    return ImageStat.Stat(near, mask).mean[0] / 255


def erasure_of(original: Image.Image, plan: Plan, others: list[Box]) -> Erasure:
    """The plan tightened to the lines of letters its box reaches, each an area; else its box."""
    size = Size(*original.size)
    colour = dominant_colour(original, plan.fill)
    found = letter_lines(original, plan.text, colour, others)
    if found:
        tight = retexted(plan, box_around(found), size)
        if not any(shared_area(tight.erase, o) for o in others):
            areas = tuple(padded_inside(original, line, LINE_PAD, colour) for line in found)
            return Erasure(tight, Ground(colour, ink_on(colour)), areas)
    return Erasure(plan, ground(original, plan), (plan.erase,))


def erasures_of(original: Image.Image, planned: list[Plan]) -> list[Erasure]:
    """Each plan, tightened where it can be, with what is under its text on the original page."""
    return [erasure_of(original, p, [q.text for q in planned if q is not p]) for p in planned]


def _fill_contents(found: Ground) -> dict[str, JsonValue]:
    if found.colour is None:
        return {"contents": "contentAware"}
    return {"contents": "color", "color": hex_of(found.colour)}


def _select_steps(areas: tuple[Box, ...]) -> list[BatchStep]:
    """One select.rect per area, the first replacing the selection and the rest adding to it."""
    return [
        BatchStep(
            command="select.rect",
            params={"x": x, "y": y, "width": w, "height": h, "mode": "add" if n else "replace"},
        )
        for n, (x, y, w, h) in enumerate(areas)
    ]


def erase_steps(erasures: list[Erasure]) -> list[BatchStep]:
    """For each erasure, select all its areas and fill them once; then drop the selection."""
    steps: list[BatchStep] = []
    for erasure in erasures:
        steps.extend(_select_steps(erasure.areas))
        steps.append(BatchStep(command="edit.fill", params=_fill_contents(erasure.ground)))
    return [*steps, BatchStep(command="select.deselect", params={})]


def missed_erasures(erasures: list[Erasure], results: list[StepResult]) -> list[str]:
    """Each erasure whose selects or fill PhotoCraft refused, with PhotoCraft's reason."""
    missed = []
    start = 0
    for erasure in erasures:
        end = start + len(erasure.areas) + 1
        refused = [step for step in results[start:end] if not step.ok]
        if refused:
            reasons = "; ".join(step.error or "refused" for step in refused)
            missed.append(f"{erasure.plan.english!r} ({reasons})")
        start = end
    return missed


def clean_page(session: Session, work: WorkFolder, name: str, erasures: list[Erasure]) -> None:
    """Writes the page's clean PNG with every area filled; refused naming each item not erased."""
    with opened(session, work.page_file(name)) as document:
        missed = missed_erasures(erasures, document.run_steps(erase_steps(erasures)))
        if missed:
            raise ComicError(f"{name}: PhotoCraft could not erase {', '.join(missed)}")
        work.clean_folder().mkdir(exist_ok=True)
        document.save(work.clean_png(name))
