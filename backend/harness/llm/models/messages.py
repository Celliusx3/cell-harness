"""The message vocabulary a model request is made of."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from harness.llm.models.blocks import Block, Image, Text
from harness.llm.models.tools import ToolCall


class SystemMessage(BaseModel):
    """The instructions prepended to a request."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system"] = "system"
    content: str


class UserMessage(BaseModel):
    """The person's prompt, and the images it shows, as the model sees them."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user"] = "user"
    content: str
    images: tuple[Image, ...] = ()


class ApplicationMessage(BaseModel):
    """Context this process put on the model-visible surface."""

    model_config = ConfigDict(frozen=True)

    role: Literal["application"] = "application"
    content: str


class AssistantMessage(BaseModel):
    """One assembled model reply, and any tool calls it asked for."""

    model_config = ConfigDict(frozen=True)

    role: Literal["assistant"] = "assistant"
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


class ToolMessage(BaseModel):
    """What one tool call returned, addressed back to it by `tool_call_id`."""

    model_config = ConfigDict(frozen=True)

    role: Literal["tool"] = "tool"
    tool_call_id: str
    content: tuple[Block, ...]

    @field_validator("content", mode="before")
    @classmethod
    def _wrap_text(cls, value: object) -> object:
        """A plain string is one text block."""
        return (Text(text=value),) if isinstance(value, str) else value


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage


def images_of(message: Message) -> tuple[Image, ...]:
    """The images a message shows the model, oldest first."""
    if isinstance(message, UserMessage):
        return message.images
    if isinstance(message, ToolMessage):
        return tuple(block for block in message.content if isinstance(block, Image))
    return ()
