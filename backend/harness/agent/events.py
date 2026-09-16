"""What a `run()` stream yields.

An agent's output is a superset of the LLM's: it passes `TextChunk` through live
and adds the two terminals below. Distinct `kind` strings, deliberately — a
consumer switching on `kind` must not confuse the LLM call ending with the
*agent* ending, which in phase 2 are no longer the same moment.

`AgentEvent` is a Protocol rather than a closed union, for one reason: a closed
union would have to name every agent kind's events, so adding one would mean
editing this module. The router in phase 10 declares its own terminal and
satisfies this structurally.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


@runtime_checkable
class AgentEvent(Protocol):
    """`kind` identifies the event; `model_dump_json` puts it on the wire."""

    kind: str

    def model_dump_json(self) -> str: ...


class ToolProgress(BaseModel):
    """A running tool reporting how far along it is.

    Zero or more of these precede the single `ToolResult` carrying the same
    `tool_call_id`, which is what lets a consumer attach the reading to the call
    it belongs to. `percent` is `None` when the total is not knowable.

    Not logged: the session records durable facts, and a progress reading is
    neither durable nor a fact about the conversation. A replayed turn therefore
    has no progress at all, so anything rendering these must tolerate absence.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_progress"] = "tool_progress"
    tool_call_id: str
    name: str
    percent: float | None
    message: str | None


class ToolResult(BaseModel):
    """A settled tool call, as the model will see it.

    `content` is already rendered — a failure wears its `error: ` prefix — so a
    consumer never has to know the outcome was typed. The typed code lives on the
    `tool/result` session event beside it.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    name: str
    content: str


class ToolPending(BaseModel):
    """One call's turn is over without a result: the client answers it later."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_pending"] = "tool_pending"
    tool_call_id: str
    name: str


class AgentCompleted(BaseModel):
    """Terminal: the turn finished. `text` is the final reply."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["agent_completed"] = "agent_completed"
    text: str


class AgentPending(BaseModel):
    """Terminal: the turn stopped for the person to answer a client tool.

    Not a failure and not completion. The call named here has no result in
    the log; the turn that supplies one — or answers it as skipped — is the
    next one.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["agent_pending"] = "agent_pending"
    tool_call_id: str
    name: str


class AgentFailed(BaseModel):
    """Terminal: the turn stopped without completing.

    A provider error, or a contract violation such as a stream that ended with no
    terminal event. Not an exception: the conversation survives, and the next
    turn can proceed.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["agent_failed"] = "agent_failed"
    reason: str
