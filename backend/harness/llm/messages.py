"""The message vocabulary a model request is made of."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolCall(BaseModel):
    """One invocation the model asked for."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: str


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


class UserMessage(BaseModel):
    """The person's prompt, as the model sees it."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user"] = "user"
    content: str


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


Block = Annotated[Text | ToolReference, Field(discriminator="type")]


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

    @property
    def text(self) -> str:
        return render_text(self.content)


def render_text(blocks: tuple[Block, ...]) -> str:
    """The prose of a result: its text blocks, joined."""
    return "\n\n".join(block.text for block in blocks if isinstance(block, Text))


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage
