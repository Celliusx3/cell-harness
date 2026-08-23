"""The event vocabulary — the durable facts an interaction is made of.

Nine types: turn and step boundaries, the messages on the model-visible surface,
the raw stream, and the tool calls a step made. Compaction adds its own trio
later. The union is closed and every member is a Pydantic model with concrete
field types, which is what makes the log losslessly serializable without a
runtime check on every append.

A **step** is one model request plus the tools it asked for; a **turn** is one or
more steps. Phase 1 had no steps because a turn without tools is exactly one
request; now that a tool result can force another request, the distinction is
what the loop iterates over and what a UI groups by.

Why chunks are events at all: a durable `assistant/chunk` is what makes replay
token-faithful. A UI reattaching to a running turn, or rendering a finished one,
draws from the same stream the live client saw. Without them, replay reproduces
the answer but not the experience of receiving it.

`turn/end` is recorded even for a turn that produced nothing. A rejected or
failed attempt is a fact about the conversation, and a log that omits it cannot
distinguish "never asked" from "asked and got nothing".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from harness.llm.messages import AssistantMessage, ToolCall, ToolMessage, UserMessage
from harness.llm.stream import StreamEvent, Usage


class TurnStart(BaseModel):
    """Opens turn `turn`, before any input is claimed."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn/start"] = "turn/start"
    turn: int


# Why a turn ended. `completed` is the only success; the rest each say something
# a consumer acts on differently — a UI shows an error for `failed`, nothing for
# `cancelled`, and a retry affordance for neither.
TurnEndReason = Literal["completed", "failed", "cancelled"]


class TurnEnd(BaseModel):
    """Closes turn `turn` with the reason it ended."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn/end"] = "turn/end"
    turn: int
    reason: TurnEndReason


class UserMessageEvent(BaseModel):
    """A user-role message entering the model-visible surface."""

    model_config = ConfigDict(frozen=True)

    type: Literal["user/message"] = "user/message"
    turn: int
    message: UserMessage


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
    """The model asked for one tool invocation.

    Recorded before the tool runs, so the log shows what was attempted even if
    the process dies mid-call. `call.arguments` is the model's raw JSON string,
    unparsed — arguments that fail to parse are a normal failure the model
    recovers from, and a log that could not hold them could not replay the turn
    that produced one.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["tool/call"] = "tool/call"
    turn: int
    step: int
    call: ToolCall


class ToolResultEvent(BaseModel):
    """What one tool call returned.

    `message` is the model-facing result, already rendered — a `Failure` wears
    its `error: ` prefix here. `error` keeps the typed identity beside it, which
    is what the phase-8 guardrail counts rather than re-deriving intent from a
    string prefix.

    Phase 4 adds tool-private presentation data here once a UI renders cards.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["tool/result"] = "tool/result"
    turn: int
    step: int
    message: ToolMessage
    error: str | None = None


class AssistantMessageEvent(BaseModel):
    """The assembled reply for one turn, and its token accounting.

    `usage` travels with the message rather than in a record of its own, because
    the two are one fact: this output cost that much. Absent when the provider
    reported none.

    `interrupted` marks a reply finalized from the prefix the user actually saw
    after a turn was cancelled mid-stream. It distinguishes that from a complete
    short answer, which is otherwise indistinguishable in the log.
    """

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
    | AssistantChunk
    | AssistantMessageEvent
    | ToolCallEvent
    | ToolResultEvent
)
