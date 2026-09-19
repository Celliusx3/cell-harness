"""Client tools end to end: what is declared, and how an answer is accepted."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from pydantic import ValidationError

from harness.session.log import Session
from harness.tools.client.catalog import ClientTools
from harness.tools.client.pending import PendingCall, pending_call
from harness.tools.definition import Failure, Ok, ToolDefinition


class Refused(Enum):
    """Why an answer was not taken."""

    NOT_PENDING = "not_pending"
    DOES_NOT_FIT = "does_not_fit"


@dataclass(frozen=True)
class Accepted:
    """An answer that fits: what the resumed turn opens with."""

    call_id: str
    outcome: Ok | Failure


class ClientToolService:
    """The declared client tools, and the one way to answer any of them."""

    def __init__(self, tools: ClientTools) -> None:
        self._tools = tools

    @property
    def names(self) -> frozenset[str]:
        """What is offered, withheld from scripts, and asked of chats."""
        return self._tools.names

    def definitions(self) -> list[ToolDefinition]:
        """The tools to register."""
        return self._tools.definitions()

    def pending(self, session: Session) -> PendingCall | None:
        """The call a client may answer right now, if any."""
        return pending_call(session, self.names)

    def accept_call(self, session: Session, call_id: str, raw: object) -> Accepted | Refused:
        """An answer from a client that read the call id off the stream."""
        return self._accept(session, raw, lambda pending: pending.call_id == call_id)

    def accept_tool(self, session: Session, name: str, raw: object) -> Accepted | Refused:
        """An answer from a client that knows only which tool it is answering."""
        return self._accept(session, raw, lambda pending: pending.name == name)

    def _accept(
        self, session: Session, raw: object, expected: Callable[[PendingCall], bool]
    ) -> Accepted | Refused:
        pending = self.pending(session)
        if pending is None or not expected(pending):
            return Refused.NOT_PENDING
        try:
            output = self._tools.parse(pending.name, raw)
        except ValidationError:
            return Refused.DOES_NOT_FIT
        return Accepted(pending.call_id, self._tools.outcome(output))
