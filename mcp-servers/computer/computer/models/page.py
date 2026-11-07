"""What the page tools take and return: an action on the open page, and the page it leaves."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActionKind = Literal["click", "fill", "type"]


class Action(BaseModel):
    """One step on the open page; fill replaces a field's value, type adds to it."""

    model_config = ConfigDict(frozen=True)

    kind: ActionKind
    ref: str = Field(min_length=1, description="From the newest page content.")
    text: str | None = Field(default=None, description="Required for fill and type; not click.")

    @model_validator(mode="after")
    def text_fits_kind(self) -> Self:
        if self.kind == "click" and self.text is not None:
            raise ValueError("click takes no text")
        if self.kind != "click" and self.text is None:
            raise ValueError(f"{self.kind} needs text")
        return self


class Opened(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str


class Page(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    content: str


class Acted(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    content: str
    actions_completed: int
