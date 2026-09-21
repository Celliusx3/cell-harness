"""Client tools end to end: what is declared, and how an answer is accepted."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from pydantic import ValidationError

from harness.session.log import Session
from harness.tools.approval import DENIED, DENIED_RESULT, ApprovalGate, Approved, parse_decision
from harness.tools.client.catalog import ClientTools
from harness.tools.client.pending import PendingCall, pending_calls
from harness.tools.definition import Failure, Ok, ToolDefinition


class Refused(Enum):
    """Why an answer was not taken."""

    NOT_PENDING = "not_pending"
    DOES_NOT_FIT = "does_not_fit"


@dataclass(frozen=True)
class Accepted:
    """An answer that fits: what the resumed turn opens with."""

    call_id: str
    outcome: Ok | Failure | Approved


class ClientToolService:
    """The declared client tools, the approval gate, and the one way to answer either."""

    def __init__(self, tools: ClientTools, gate: ApprovalGate) -> None:
        if both := tools.names & gate.tools:
            raise ValueError(f"{sorted(both)} are both client tools and tools that ask")
        self._tools = tools
        self._gate = gate

    @property
    def names(self) -> frozenset[str]:
        """The client tools: offered, withheld from scripts, and asked of chats."""
        return self._tools.names

    @property
    def gated(self) -> frozenset[str]:
        """The tools that ask the person before running; a chat asks them with buttons."""
        return self._gate.tools

    @property
    def awaited(self) -> frozenset[str]:
        """Every tool whose call waits on the person — client tools and tools that ask."""
        return self._tools.names | self._gate.tools

    def definitions(self) -> list[ToolDefinition]:
        """The tools to register."""
        return self._tools.definitions()

    def pending(self, session: Session) -> tuple[PendingCall, ...]:
        """The calls a client may answer right now, in log order."""
        return pending_calls(session, self.awaited)

    def accept_call(self, session: Session, call_id: str, raw: object) -> Accepted | Refused:
        """An answer from a client that read the call id off the stream."""
        return self._accept(session, raw, lambda pending: pending.call_id == call_id)

    def accept_tool(self, session: Session, name: str, raw: object) -> Accepted | Refused:
        """An answer from a client that knows only which tool it is answering."""
        return self._accept(session, raw, lambda pending: pending.name == name)

    def _accept(
        self, session: Session, raw: object, expected: Callable[[PendingCall], bool]
    ) -> Accepted | Refused:
        pending = next((p for p in self.pending(session) if expected(p)), None)
        if pending is None:
            return Refused.NOT_PENDING
        if pending.name in self._gate.tools:
            return self._decide(pending, raw)
        try:
            output = self._tools.parse(pending.name, raw)
        except ValidationError:
            return Refused.DOES_NOT_FIT
        return Accepted(pending.call_id, self._tools.outcome(output))

    def _decide(self, pending: PendingCall, raw: object) -> Accepted | Refused:
        try:
            decision = parse_decision(raw)
        except ValidationError:
            return Refused.DOES_NOT_FIT
        if not isinstance(decision, Approved):
            return Accepted(pending.call_id, Failure(DENIED, DENIED_RESULT))
        if decision.scope == "always":
            self._gate.grant(pending.name)
        return Accepted(pending.call_id, decision)
