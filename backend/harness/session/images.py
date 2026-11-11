"""The hide of the log's oldest images, and the folds that read it back."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from harness.llm import Image, Text, ToolMessage, UserMessage
from harness.prompts import IMAGE_NOT_SHOWN

if TYPE_CHECKING:
    from harness.session.models import SessionEvent


class ImagesHidden(BaseModel):
    """The first `through` images of the chat's log are hidden from the model from here on."""

    model_config = ConfigDict(frozen=True)

    type: Literal["images/hidden"] = "images/hidden"
    turn: int | None
    through: int = Field(ge=0)


def hidden_through(events: Sequence[SessionEvent]) -> int:
    """How many of the log's first images are hidden: the largest hide logged, or 0."""
    return max((event.through for event in events if isinstance(event, ImagesHidden)), default=0)


def first_images_noted[M: (UserMessage, ToolMessage)](message: M, count: int) -> M:
    """`message` with its first `count` images each replaced by IMAGE_NOT_SHOWN."""
    if count == 0:
        return message
    if isinstance(message, UserMessage):
        notes = "\n".join([IMAGE_NOT_SHOWN] * count)
        return UserMessage(content=f"{message.content}\n{notes}", images=message.images[count:])
    positions = [i for i, block in enumerate(message.content) if isinstance(block, Image)]
    noted = frozenset(positions[:count])
    content = tuple(
        Text(text=IMAGE_NOT_SHOWN) if index in noted else block
        for index, block in enumerate(message.content)
    )
    return ToolMessage(tool_call_id=message.tool_call_id, content=content)
