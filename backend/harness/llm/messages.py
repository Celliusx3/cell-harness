"""The message vocabulary a model request is made of."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

ExtraContent = dict[str, JsonValue]


class ToolCall(BaseModel):
    """One invocation the model asked for."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: str
    extra_content: ExtraContent | None = None
    """What the provider attached to this call and needs back with it; only its adapter reads it."""


class ToolSpec(BaseModel):
    """What the model is told about one tool."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict


class SystemMessage(BaseModel):
    """The instructions prepended to a request."""

    model_config = ConfigDict(frozen=True)

    role: Literal["system"] = "system"
    content: str


class Image(BaseModel):
    """An image the model is shown, stored once by the hash of its bytes."""

    model_config = ConfigDict(frozen=True)

    type: Literal["image"] = "image"
    media_type: str
    sha256: str
    size: int = 0


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


Block = Annotated[Text | ToolReference | Image, Field(discriminator="type")]


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


def render_text(blocks: tuple[Block, ...]) -> str:
    """The prose of a result: its text blocks, joined."""
    return "\n\n".join(block.text for block in blocks if isinstance(block, Text))


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage


def images_of(message: Message) -> tuple[Image, ...]:
    """The images a message shows the model, oldest first."""
    if isinstance(message, UserMessage):
        return message.images
    if isinstance(message, ToolMessage):
        return tuple(block for block in message.content if isinstance(block, Image))
    return ()
