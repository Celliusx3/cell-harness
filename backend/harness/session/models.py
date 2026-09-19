"""The data types a session deals in — events, and the header beside them."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from harness.llm.messages import (
    ApplicationMessage,
    AssistantMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from harness.llm.stream import StreamEvent, Usage
from harness.session.compaction import CompactionEnd, CompactionPrune, CompactionStart
from harness.tools.definition import ToolUi

SESSION_FORMAT_VERSION = 1


class SessionHeader(BaseModel):
    """Immutable storage metadata for one session."""

    model_config = ConfigDict(frozen=True)

    type: Literal["session"] = "session"
    version: int = SESSION_FORMAT_VERSION
    id: str = Field(min_length=1)
    created_at: datetime
    title: str = ""


class TurnStart(BaseModel):
    """Opens turn `turn`, before any input is claimed."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn/start"] = "turn/start"
    turn: int


TurnEndReason = Literal["completed", "failed", "cancelled", "pending"]


class TurnEnd(BaseModel):
    """Closes turn `turn` with the reason it ended."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn/end"] = "turn/end"
    turn: int
    reason: TurnEndReason


class UserMessageEvent(BaseModel):
    """The person's message entering the model-visible surface."""

    model_config = ConfigDict(frozen=True)

    type: Literal["user/message"] = "user/message"
    turn: int
    message: UserMessage


class ApplicationMessageEvent(BaseModel):
    """Context this process injected into the model-visible history."""

    model_config = ConfigDict(frozen=True)

    type: Literal["application/message"] = "application/message"
    turn: int
    message: ApplicationMessage


class StepStart(BaseModel):
    """Opens step `step` of turn `turn` — one model request and its tools."""

    model_config = ConfigDict(frozen=True)

    type: Literal["step/start"] = "step/start"
    turn: int
    step: int


class StepEnd(BaseModel):
    """Closes step `step` of turn `turn`."""

    model_config = ConfigDict(frozen=True)

    type: Literal["step/end"] = "step/end"
    turn: int
    step: int


class AssistantChunk(BaseModel):
    """One raw stream fragment, kept for replay fidelity."""

    model_config = ConfigDict(frozen=True)

    type: Literal["assistant/chunk"] = "assistant/chunk"
    turn: int
    step: int
    chunk: StreamEvent


class ToolCallEvent(BaseModel):
    """The model asked for one tool invocation."""

    model_config = ConfigDict(frozen=True)

    type: Literal["tool/call"] = "tool/call"
    turn: int
    step: int
    call: ToolCall


class ToolResultEvent(BaseModel):
    """What one tool call returned."""

    model_config = ConfigDict(frozen=True)

    type: Literal["tool/result"] = "tool/result"
    turn: int
    step: int
    message: ToolMessage
    error: str | None = None
    ui: ToolUi | None = None


class AssistantMessageEvent(BaseModel):
    """The assembled reply for one turn, and its token accounting."""

    model_config = ConfigDict(frozen=True)

    type: Literal["assistant/message"] = "assistant/message"
    turn: int
    step: int
    message: AssistantMessage
    usage: Usage | None = None
    interrupted: bool = False


SessionEvent = (
    TurnStart
    | TurnEnd
    | StepStart
    | StepEnd
    | UserMessageEvent
    | ApplicationMessageEvent
    | AssistantChunk
    | AssistantMessageEvent
    | ToolCallEvent
    | ToolResultEvent
    | CompactionStart
    | CompactionEnd
    | CompactionPrune
)
