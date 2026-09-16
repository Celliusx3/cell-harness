"""The data types a session deals in — events, and the header beside them.

Two kinds of thing, both plain frozen Pydantic models with no behaviour:

**Events** are the durable facts an interaction is made of. The union is closed
and every member has concrete field types, which is what makes the log losslessly
serializable without a runtime check on every append.

A **step** is one model request plus the tools it asked for; a **turn** is one or
more steps. Phase 1 had no steps because a turn without tools is exactly one
request; now that a tool result can force another request, the distinction is
what the loop iterates over and what a UI groups by.

Why chunks are events at all: a durable `assistant/chunk` is what makes replay
token-faithful. A UI reattaching to a running turn, or rendering a finished one,
draws from the same stream the live client saw. Without them, replay reproduces
the answer but not the experience of receiving it.

`turn/end` is recorded even for a turn that produced nothing. A rejected or failed
attempt is a fact about the conversation, and a log that omits it cannot
distinguish "never asked" from "asked and got nothing".

**The header** is the other kind: a format version, an id, a creation time and a
title are *storage* concerns, not things that happened in the conversation. They
are deliberately not events, so they never reach `derive_messages` and can never
leak into a model request. The practical consequence: there is no
`conversation/renamed` event, ever.
"""

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
from harness.tools.definition import ToolUi

# Stamped into every header written. A backend refuses any other version on load
# rather than guessing: migration is a real feature, and best-effort parsing of a
# format we do not understand is how a log becomes quietly unreadable.
SESSION_FORMAT_VERSION = 1


class SessionHeader(BaseModel):
    """Immutable storage metadata for one session.

    `type: "session"` is deliberately slash-less. Every event type contains a `/`
    (`turn/start`, `tool/call`, …), so a header line and an event line can never
    be confused — even by a reader that lost track of which line it was on.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["session"] = "session"
    version: int = SESSION_FORMAT_VERSION
    id: str = Field(min_length=1)
    created_at: datetime
    # Stamped once, at first append, from the conversation's first user message —
    # see `persist.py`. Empty until then, and empty forever for a session that
    # never had one. Renaming is a later phase and will need a mutable sidecar,
    # because this line is written exactly once and the file is append-only.
    title: str = ""


class TurnStart(BaseModel):
    """Opens turn `turn`, before any input is claimed."""

    model_config = ConfigDict(frozen=True)

    type: Literal["turn/start"] = "turn/start"
    turn: int


# Why a turn ended. `completed` is the only success; the rest each say something
# a consumer acts on differently — a UI shows an error for `failed`, nothing for
# `cancelled`, and a retry affordance for neither.
# `pending`: the model asked the client for something and the turn stopped for
# the person to answer — deliberate, so a call it leaves unanswered is not a
# crash for `repair` and not a cancellation for the screen.
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
    """Context this process injected — the guardrail telling the model it is
    repeating itself is the first; phase 16's `inject()` is the next.

    Its own event, not a flag on `user/message`: it reaches the model in the
    user role (Claude Code's reminder shape, see `derive_messages`), but it is
    not something the person said, so the title and the UI must be able to tell
    without a second field to remember. dsh's `MessageSource.kind` is the
    precedent.
    """

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

    `message` is the tool's result, already rendered — a `Failure` wears its
    `error: ` prefix here, and nothing the harness adds is ever mixed in: a
    hook's guidance is its own `application/message`, so "was this result the same as
    the last one?" compares the tool's words alone. `error` keeps the typed
    identity beside it, which is what the guardrail counts rather than
    re-deriving intent from a string prefix. `ui` is the one thing here the
    model does not see: an MCP App bound to the tool, logged because the browser
    renders a conversation from this log and nothing else.
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["tool/result"] = "tool/result"
    turn: int
    step: int
    message: ToolMessage
    error: str | None = None
    ui: ToolUi | None = None


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
    | ApplicationMessageEvent
    | AssistantChunk
    | AssistantMessageEvent
    | ToolCallEvent
    | ToolResultEvent
)
