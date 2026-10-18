"""The data types a session deals in — events, and the header beside them."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from harness.files.models import ChatFile
from harness.llm import (
    ApplicationMessage,
    AssistantMessage,
    StreamEvent,
    ToolCall,
    ToolMessage,
    Usage,
    UserMessage,
)
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
    numbered_from: int = Field(default=0, description="The number of this file's first event.")


class TurnStart(BaseModel):
    """Opens turn `turn` for the bot `bot_id`, before any input is claimed."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn/start"] = "turn/start"
    turn: int
    bot_id: str | None = Field(default=None, description="The speaker; None in older logs.")


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
    files: tuple[ChatFile, ...] = ()


BotMessageIntent = Literal["request", "result"]


class BotMessage(BaseModel):
    """What one bot sent another: who from, the text, how many hops it has come, and why."""

    model_config = ConfigDict(frozen=True)

    from_bot_id: str
    from_name: str
    text: str
    hop: int
    intent: BotMessageIntent


class BotMessageEvent(BaseModel):
    """Another bot's message entering this chat, opening the turn that answers it."""

    model_config = ConfigDict(frozen=True)

    type: Literal["bot/message"] = "bot/message"
    turn: int
    message: BotMessage


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
    files: tuple[ChatFile, ...] = ()


class AssistantMessageEvent(BaseModel):
    """The assembled reply for one turn, and its token accounting."""

    model_config = ConfigDict(frozen=True)

    type: Literal["assistant/message"] = "assistant/message"
    turn: int
    step: int
    message: AssistantMessage
    usage: Usage | None = None
    interrupted: bool = False


class ApprovalGrant(BaseModel):
    """The person allowed `tool` to run unasked for the rest of this conversation."""

    model_config = ConfigDict(frozen=True)

    type: Literal["approval/grant"] = "approval/grant"
    turn: int
    tool: str


class BotInstructionsEvent(BaseModel):
    """A bot answering in this conversation, as its turns from here on are prompted."""

    model_config = ConfigDict(frozen=True)

    type: Literal["bot/instructions"] = "bot/instructions"
    name: str
    instructions: str
    bot_id: str | None = Field(default=None, description="The bot; None in older logs.")


class GroupMembersEvent(BaseModel):
    """The group this conversation belongs to, and its members' names, as its bots are told."""

    model_config = ConfigDict(frozen=True)

    type: Literal["group/members"] = "group/members"
    name: str
    members: tuple[str, ...]


class ChatCleared(BaseModel):
    """The person cleared this chat: the model's history and the timeline start after it."""

    model_config = ConfigDict(frozen=True)

    type: Literal["chat/cleared"] = "chat/cleared"


SessionEvent = (
    TurnStart
    | TurnEnd
    | StepStart
    | StepEnd
    | UserMessageEvent
    | BotMessageEvent
    | ApplicationMessageEvent
    | AssistantChunk
    | AssistantMessageEvent
    | ToolCallEvent
    | ToolResultEvent
    | CompactionStart
    | CompactionEnd
    | CompactionPrune
    | ApprovalGrant
    | BotInstructionsEvent
    | GroupMembersEvent
    | ChatCleared
)
