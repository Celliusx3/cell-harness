"""What pages.json and translations.json hold, and the boxes, sizes and colours of a page."""

from __future__ import annotations

from typing import Annotated, NamedTuple, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

THOUSAND = 1000


class Corners(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int


class Box(NamedTuple):
    x: int
    y: int
    w: int
    h: int

    def corners(self) -> Corners:
        """The box's edges, the way PIL crops and pastes."""
        return Corners(self.x, self.y, self.x + self.w, self.y + self.h)


class Colour(NamedTuple):
    red: int
    green: int
    blue: int


class Size(NamedTuple):
    width: int
    height: int


class Page(BaseModel):
    """A page in pages.json: its file under pages/, its size and its parts' areas, top to bottom."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    page: str
    size: Size
    parts: list[Box] = Field(min_length=1)


Box2D = Annotated[
    tuple[Annotated[int, Field(ge=0, le=THOUSAND)], ...], Field(min_length=4, max_length=4)
]


class Item(BaseModel):
    """One bubble or caption: the part showing it, its text's box there, its text, its English."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    part: int
    box_2d: Box2D
    original: str = Field(min_length=1)
    english: str = Field(min_length=1)

    @model_validator(mode="after")
    def _is_ordered(self) -> Self:
        ymin, xmin, ymax, xmax = self.box_2d
        if ymin >= ymax or xmin >= xmax:
            raise ValueError(
                f"the item {self.english!r} has box_2d {list(self.box_2d)}; "
                "ymin must be under ymax and xmin under xmax"
            )
        return self


class Translation(BaseModel):
    """A page in translations.json: how many times it has been written, and its last items."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt: int = Field(ge=1)
    items: list[Item]


PAGES = TypeAdapter(list[Page])
ITEMS = TypeAdapter(list[Item])
TRANSLATIONS = TypeAdapter(dict[str, Translation])
