"""pages: unpack a comic into its work folder, and list its pages, their parts and their views."""

from __future__ import annotations

import logging
import re
import shutil
import zipfile
from pathlib import Path

from PIL import Image

from comic import ComicError
from comic.chapter.pages import PAGES, Page, Size
from comic.chapter.parts import part_areas
from comic.chapter.work import WorkFolder
from comic.models import ListedPage, PagesResult
from comic.steps import absolute_path
from comic.steps.view import page_views

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
WORK_SUFFIX = "-english"

logger = logging.getLogger("comic.pages")


def natural_key(name: str) -> list[str | int]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def copy_pages(source: Path, pages: Path) -> list[Path]:
    """The source's pages copied to pages/ as 001.ext, 002.ext, ... in natural name order."""
    pages.mkdir(parents=True)
    if source.is_dir():
        found = sorted(
            (p for p in source.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES),
            key=lambda p: natural_key(p.name),
        )
        for number, path in enumerate(found, start=1):
            shutil.copyfile(path, pages / f"{number:03d}{path.suffix.lower()}")
    elif source.suffix.lower() in IMAGE_SUFFIXES:
        shutil.copyfile(source, pages / f"001{source.suffix.lower()}")
    else:
        with zipfile.ZipFile(source) as archive:
            entries = sorted(
                (
                    e
                    for e in archive.namelist()
                    if Path(e).suffix.lower() in IMAGE_SUFFIXES and "__MACOSX" not in e
                ),
                key=natural_key,
            )
            for number, entry in enumerate(entries, start=1):
                (pages / f"{number:03d}{Path(entry).suffix.lower()}").write_bytes(
                    archive.read(entry)
                )
    return sorted(pages.iterdir(), key=lambda p: natural_key(p.name))


def page_at(path: Path) -> Page:
    """The page at `path` as pages.json holds it: its name, its size and its parts' areas."""
    with Image.open(path) as image:
        size = Size(*image.size)
    return Page(page=path.name, size=size, parts=part_areas(size))


def unpack_comic(work: WorkFolder, source: Path) -> None:
    """Every page unpacked into pages/ and measured, then the folder marked unpacked."""
    shutil.rmtree(work.pages_folder(), ignore_errors=True)
    paths = copy_pages(source, work.pages_folder())
    if not paths:
        raise ComicError(f"no {', '.join(IMAGE_SUFFIXES)} pages in {source}")
    pages = [page_at(path) for path in paths]
    work.pages_json().write_bytes(PAGES.dump_json(pages, indent=1))
    logger.info("%s: %d pages", source.name, len(pages))


def list_pages(path: str) -> PagesResult:
    """The comic's pages, their parts and each part's view, unpacked once into a work folder."""
    source = absolute_path(path)
    if not source.exists():
        raise ComicError(f"{path} does not exist")
    work = WorkFolder(source.parent / f"{source.stem}{WORK_SUFFIX}")
    if not work.is_unpacked():
        unpack_comic(work, source)
    return PagesResult(
        work=str(work.root),
        pages=[
            ListedPage(page=page.page, parts=len(page.parts), views=page_views(work, page))
            for page in work.pages()
        ],
    )
