"""What a `run()` stream yields."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


@runtime_checkable
class AgentEvent(Protocol):
    """`kind` identifies the event; `model_dump_json` puts it on the wire."""

    kind: str

    def model_dump_json(self) -> str: ...


class ToolProgress(BaseModel):
    """A running tool reporting how far along it is."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_progress"] = "tool_progress"
    tool_call_id: str
    name: str
    percent: float | None
    message: str | None


class ToolResult(BaseModel):
    """A settled tool call, as the model will see it."""

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
    """Terminal: the turn stopped for the person to answer a client tool."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["agent_pending"] = "agent_pending"
    tool_call_id: str
    name: str


class AgentFailed(BaseModel):
    """Terminal: the turn stopped without completing."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["agent_failed"] = "agent_failed"
    reason: str
