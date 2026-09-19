"""What a streaming completion yields, event by event."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from harness.llm.messages import ToolCall


class Usage(BaseModel):
    """Token accounting for one model call, when the provider reported it."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int
    output_tokens: int


class TextChunk(BaseModel):
    """A fragment of the reply as it arrives."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text"] = "text"
    text: str


class ToolCallChunk(BaseModel):
    """A tool call, once the adapter has assembled it."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_call"] = "tool_call"
    call: ToolCall


class Completed(BaseModel):
    """Terminal: the model finished."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["completed"] = "completed"
    full_text: str
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage | None = None


CONTEXT_WINDOW_EXCEEDED = "context_window_exceeded"


class Failed(BaseModel):
    """Terminal: the call did not produce a reply."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["failed"] = "failed"
    reason: str
    code: str | None = None


StreamEvent = TextChunk | ToolCallChunk | Completed | Failed
