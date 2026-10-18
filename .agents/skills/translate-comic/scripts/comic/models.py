"""What the commands print."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from comic.chapter.pages import Box2D


class ListedPage(BaseModel):
    """A page of the comic, how many parts it is shown in, and each part's JPEG, top to bottom."""

    model_config = ConfigDict(frozen=True)

    page: str
    parts: int
    views: list[str]


class PagesResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    work: str
    pages: list[ListedPage]


class LeftOver(BaseModel):
    """An area of the erased page that still looks like text, named as an item names its box."""

    model_config = ConfigDict(frozen=True)

    part: int
    box_2d: Box2D


class WriteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: str
    attempt: int
    english: str
    views: list[str]
    cut_off: list[str]
    spills: list[str]
    left_over: list[LeftOver]


class CleanupResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    kept: str
    removed_files: int
    freed_bytes: int
