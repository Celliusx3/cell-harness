"""The write step for one page."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from comic.chapter.pages import TRANSLATIONS, Item, Translation
from comic.chapter.plan import plans_of
from comic.chapter.work import WorkFolder, rgb_image
from comic.connection import connected
from comic.lettering.bubble import placements
from comic.lettering.clean import Erasure, clean_page, erasures_of
from comic.lettering.leftover import left_over_at, text_areas
from comic.lettering.spills import spilling_lines
from comic.lettering.text_layers import letter_clean_page
from comic.lock import held
from comic.models import LeftOver, WriteResult
from comic.steps import page_of
from comic.steps.view import english_views

logger = logging.getLogger("comic.write")


@dataclass(frozen=True)
class PhotoCraftAccess:
    """Where PhotoCraft's server listens, its token, and the lock that lets one script in."""

    addr: str
    token: str
    lock: Path


def left_over(work: WorkFolder, name: str) -> list[LeftOver]:
    """Where the clean page still looks like text in a bubble, named as an item names its box."""
    page = page_of(work, name)
    cleaned = np.asarray(rgb_image(work.clean_png(name)))
    return [left_over_at(page, area) for area in text_areas(cleaned)]


def record_attempt(work: WorkFolder, name: str, items: Sequence[Item]) -> int:
    """The page's items saved in translations.json with one more attempt counted; that count."""
    kept = work.translations() if work.translations_json().is_file() else {}
    previous = kept.get(name)
    attempt = 1 if previous is None else previous.attempt + 1
    entries = {**kept, name: Translation(attempt=attempt, items=list(items))}
    work.translations_json().write_bytes(TRANSLATIONS.dump_json(entries, indent=1))
    return attempt


def letter_page(
    access: PhotoCraftAccess, work: WorkFolder, name: str, erased: list[Erasure]
) -> list[str]:
    """The page erased and lettered by PhotoCraft; the lines that did not fit."""
    with connected(access.addr, access.token) as session:
        clean_page(session, work, name, erased)
        placed = placements(rgb_image(work.clean_png(name)), erased)
        work.english_folder().mkdir(exist_ok=True)
        outcome = letter_clean_page(session, work, name, placed)
    for english in outcome.not_created:
        logger.warning("%s: not lettered, PhotoCraft refused it: %s", name, english)
    return outcome.cut_off


def keep_page_as_is(work: WorkFolder, name: str) -> None:
    """A page with nothing to translate, saved as its own clean and English page."""
    original = rgb_image(work.page_file(name))
    for path in (work.clean_png(name), work.english_png(name)):
        path.parent.mkdir(exist_ok=True)
        original.save(path)


def write_page(
    access: PhotoCraftAccess, work: WorkFolder, name: str, items: Sequence[Item]
) -> WriteResult:
    """The page erased and lettered with `items` by PhotoCraft, its attempt and what went wrong."""
    page = page_of(work, name)
    planned = plans_of(page, list(items))
    erased = erasures_of(rgb_image(work.page_file(name)), planned)
    with held(access.lock):
        if erased:
            cut_off = letter_page(access, work, name, erased)
        else:
            keep_page_as_is(work, name)
            cut_off = []
        attempt = record_attempt(work, name, items)
    return WriteResult(
        page=name,
        attempt=attempt,
        english=str(work.english_png(name)),
        views=english_views(work, page),
        cut_off=cut_off,
        spills=spilling_lines(
            rgb_image(work.clean_png(name)),
            rgb_image(work.english_png(name)),
            [e.plan for e in erased],
        ),
        left_over=left_over(work, name),
    )
