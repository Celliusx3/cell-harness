"""The event vocabulary — the durable facts an interaction is made of.

Five types in phase 1. Tool calls, results, and step boundaries join them in
phase 2; compaction adds its own pair later. The union is closed and every
member is a Pydantic model with concrete field types, which is what makes the log
losslessly serializable without a runtime check on every append. When an event
first carries an open JSON value (phase 2's tool-result `meta`), that guarantee
ends and `Session.append` gains a validation step.

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

from harness.llm.messages import AssistantMessage, UserMessage
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


# Where a user-role message came from. Only `human` exists now; injected context
# (skill catalogs, file-change notices, job completions) arrives later wearing the
# same role on the wire, and this is what tells them apart in the log. Declared
# now because it is one word and the alternative is a schema change on the most
# frequently written event.
MessageSource = Literal["human"]


class UserMessageEvent(BaseModel):
    """A user-role message entering the model-visible surface."""

    model_config = ConfigDict(frozen=True)

    type: Literal["user/message"] = "user/message"
    turn: int
    message: UserMessage
    source: MessageSource = "human"


class AssistantChunk(BaseModel):
    """One raw stream fragment, kept for replay fidelity."""

    model_config = ConfigDict(frozen=True)

    type: Literal["assistant/chunk"] = "assistant/chunk"
    turn: int
    chunk: StreamEvent


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
    message: AssistantMessage
    usage: Usage | None = None
    interrupted: bool = False


SessionEvent = TurnStart | TurnEnd | UserMessageEvent | AssistantChunk | AssistantMessageEvent
