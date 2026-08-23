"""What a `run()` stream yields.

An agent's output is a superset of the LLM's: it passes `TextChunk` through live
and adds the two terminals below. Distinct `kind` strings, deliberately — a
consumer switching on `kind` must not confuse the LLM call ending with the
*agent* ending, which in phase 2 are no longer the same moment.

`AgentEvent` is a Protocol rather than a closed union, for one reason: a closed
union would have to name every agent kind's events, so adding one would mean
editing this module. The router in phase 9 declares its own terminal and
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


class AgentCompleted(BaseModel):
    """Terminal: the turn finished. `text` is the final reply."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["agent_completed"] = "agent_completed"
    text: str


class AgentFailed(BaseModel):
    """Terminal: the turn stopped without completing.

    A provider error, or a contract violation such as a stream that ended with no
    terminal event. Not an exception: the conversation survives, and the next
    turn can proceed.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["agent_failed"] = "agent_failed"
    reason: str
