"""The blocks a tool result is made of, and its text joined."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class Text(BaseModel):
    """Prose in a tool result — what almost every result is, entirely."""

    model_config = ConfigDict(frozen=True)

    type: Literal["text"] = "text"
    text: str


class ToolReference(BaseModel):
    """A tool this result made callable by name."""

    model_config = ConfigDict(frozen=True)

    type: Literal["tool_reference"] = "tool_reference"
    tool_name: str


class Image(BaseModel):
    """An image the model is shown, stored once by the hash of its bytes."""

    model_config = ConfigDict(frozen=True)

    type: Literal["image"] = "image"
    media_type: str
    sha256: str
    size: int


Block = Annotated[Text | ToolReference | Image, Field(discriminator="type")]


def render_text(blocks: tuple[Block, ...]) -> str:
    """The prose of a result: its text blocks, joined."""
    return "\n\n".join(block.text for block in blocks if isinstance(block, Text))
