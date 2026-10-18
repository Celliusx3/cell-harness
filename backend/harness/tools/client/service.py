"""Client tools end to end: what is declared, and how an answer is accepted."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError

from harness.prompts import DENIED_RESULT
from harness.session.log import Session
from harness.tools.approval import ApprovalGate
from harness.tools.client.catalog import ClientTools
from harness.tools.client.models import AcceptedAnswer, PendingCall, RefusalReason
from harness.tools.client.pending import pending_calls
from harness.tools.definition import ToolDefinition
from harness.tools.models.decision import DENIED, Approval, parse_decision
from harness.tools.models.outcome import Failure


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
    def gated_tools(self) -> frozenset[str]:
        """The tools that ask the person before running; a chat asks them with buttons."""
        return self._gate.tools

    @property
    def awaited_tools(self) -> frozenset[str]:
        """Every tool whose call waits on the person — client tools and tools that ask."""
        return self._tools.names | self._gate.tools

    def definitions(self) -> list[ToolDefinition]:
        """The tools to register."""
        return self._tools.definitions()

    def answerable_calls(self, session: Session) -> tuple[PendingCall, ...]:
        """The calls a client may answer right now, in log order."""
        return pending_calls(session, self.awaited_tools)

    def accept_by_call_id(
        self, session: Session, call_id: str, raw: object
    ) -> AcceptedAnswer | RefusalReason:
        """An answer from a client that read the call id off the stream."""
        return self._accept(session, raw, lambda pending: pending.call_id == call_id)

    def accept_by_tool_name(
        self, session: Session, name: str, raw: object
    ) -> AcceptedAnswer | RefusalReason:
        """An answer from a client that knows only which tool it is answering."""
        return self._accept(session, raw, lambda pending: pending.name == name)

    def _accept(
        self, session: Session, raw: object, matches: Callable[[PendingCall], bool]
    ) -> AcceptedAnswer | RefusalReason:
        pending = next((p for p in self.answerable_calls(session) if matches(p)), None)
        if pending is None:
            return RefusalReason.NOT_PENDING
        if pending.name in self._gate.tools:
            return self._accept_decision(pending, raw)
        try:
            output = self._tools.parse(pending.name, raw)
        except ValidationError:
            return RefusalReason.DOES_NOT_FIT
        return AcceptedAnswer(pending.call_id, self._tools.outcome(output))

    def _accept_decision(self, pending: PendingCall, raw: object) -> AcceptedAnswer | RefusalReason:
        try:
            decision = parse_decision(raw)
        except ValidationError:
            return RefusalReason.DOES_NOT_FIT
        if not isinstance(decision, Approval):
            return AcceptedAnswer(pending.call_id, Failure(DENIED, DENIED_RESULT))
        if decision.scope == "always":
            self._gate.grant(pending.name)
        return AcceptedAnswer(pending.call_id, decision)
