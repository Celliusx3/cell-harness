"""Writes the English as PhotoCraft text layers on the clean page, each shrunk to fit, centred."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from comic.chapter.pages import Box
from comic.chapter.plan import Plan
from comic.chapter.work import WorkFolder
from comic.connection import Session
from comic.document import BatchStep, Document, opened

SHRINK = 0.88
ROUNDS = 12


class Line(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: int
    end: int


class Bounds(NamedTuple):
    left: float
    top: float
    right: float
    bottom: float


class TypeInfo(BaseModel):
    """What PhotoCraft's type.info says of a text layer: its lines, its extent and its scale."""

    model_config = ConfigDict(frozen=True)

    lines: list[Line]
    bounds: Bounds | None = None
    px_per_pt: float = Field(alias="pxPerPt")


class CreateReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    layer: int


class Placement(NamedTuple):
    plan: Plan
    letter: Box
    color: str


class Outcome(NamedTuple):
    not_created: list[str]
    cut_off: list[str]


@dataclass(frozen=True)
class TextLayer:
    plan: Plan
    letter: Box
    layer: int
    px: int
    info: TypeInfo | None = None


def create_layers(document: Document, placed: list[Placement]) -> list[TextLayer]:
    steps: list[BatchStep] = [
        BatchStep(
            command="type.create",
            params={
                "text": p.plan.english,
                "box": list(p.letter),
                "align": "center",
                "size": p.plan.px,
                "color": p.color,
            },
        )
        for p in placed
    ]
    results = document.run_steps(steps)
    return [
        TextLayer(p.plan, p.letter, CreateReply.model_validate(r.result).layer, p.plan.px)
        for p, r in zip(placed, results, strict=True)
        if r.ok and r.result is not None
    ]


def measured_layers(document: Document, layers: list[TextLayer]) -> list[TextLayer]:
    results = document.run_steps(
        [BatchStep(command="type.info", params={"layer": t.layer}) for t in layers]
    )
    return [
        replace(
            t, info=TypeInfo.model_validate(r.result) if r.ok and r.result is not None else None
        )
        for t, r in zip(layers, results, strict=True)
    ]


def resize_layers(document: Document, layers: list[TextLayer], px_per_pt: float) -> None:
    document.run_steps(
        [
            BatchStep(command="type.setStyle", params={"layer": t.layer, "size": t.px / px_per_pt})
            for t in layers
        ]
    )


def fitted_layers(document: Document, layers: list[TextLayer], px_per_pt: float) -> list[TextLayer]:
    for _ in range(ROUNDS):
        layers = measured_layers(document, layers)
        tight = {t.layer for t in layers if not is_fitting(t) and t.px > t.plan.smallest}
        if not tight:
            return layers
        layers = [
            replace(t, px=max(t.plan.smallest, round(t.px * SHRINK))) if t.layer in tight else t
            for t in layers
        ]
        resize_layers(document, [t for t in layers if t.layer in tight], px_per_pt)
    return measured_layers(document, layers)


def is_fitting(layer: TextLayer) -> bool:
    """Every letter is laid out and the layer's extent fits its letter box."""
    info = layer.info
    if (
        info is None
        or info.bounds is None
        or not info.lines
        or info.lines[-1].end < len(layer.plan.english)
    ):
        return False
    return (
        info.bounds.right - info.bounds.left <= layer.letter.w
        and info.bounds.bottom - info.bounds.top <= layer.letter.h
    )


def _centring_steps(layers: list[TextLayer]) -> list[BatchStep]:
    return [
        BatchStep(
            command="type.edit",
            params={
                "layer": t.layer,
                "move": [
                    round(
                        t.letter.x + t.letter.w / 2 - (t.info.bounds.left + t.info.bounds.right) / 2
                    ),
                    round(
                        t.letter.y + t.letter.h / 2 - (t.info.bounds.top + t.info.bounds.bottom) / 2
                    ),
                ],
            },
        )
        for t in layers
        if t.info is not None and t.info.bounds is not None
    ]


def letter_clean_page(
    session: Session, work: WorkFolder, name: str, placed: list[Placement]
) -> Outcome:
    """Letters `placed` on the clean page, each shrunk to fit; saves the English .png."""
    with opened(session, work.clean_png(name)) as document:
        created = create_layers(document, placed)
        first = measured_layers(document, created)
        px_per_pt = next((t.info.px_per_pt for t in first if t.info is not None), 1.0)
        if px_per_pt != 1.0:
            resize_layers(document, created, px_per_pt)
        fitted = fitted_layers(document, created, px_per_pt)
        document.run_steps(_centring_steps(fitted))
        document.save(work.english_png(name))
    made = {t.plan for t in fitted}
    return Outcome(
        not_created=[p.plan.english for p in placed if p.plan not in made],
        cut_off=[t.plan.english for t in fitted if not is_fitting(t)],
    )
