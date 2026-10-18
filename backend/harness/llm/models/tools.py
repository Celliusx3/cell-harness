"""What the model calls and is told about: tool calls and tool specs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue

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
