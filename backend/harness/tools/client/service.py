"""Client tools end to end: what is declared, and how an answer is accepted.

One object for the three places that need client tools — the agent (which
tools to register), the chats and the browser route (whether an answer may
be taken, and what the model reads for it) — so the checks that make an
answer legitimate are written once. `SkillService` exists for the same
reason: one read for the page, the gateway and the model.

The checks, for any answer from anywhere: the log must hold an unanswered
call to a client tool in the current turn; if the answerer names a call it
must be that one, if it names a tool it must be that one; and the body must
fit the waiting tool's declaration. What is accepted is handed back — the
call id and the outcome the model will read — and the *caller* opens the
turn that carries it (`RunStore.resume`). This service never touches runs,
which keeps it out of the runs → agent → service cycle.
"""

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

    # No client-tool call is pending, or not the one the answerer named.
    NOT_PENDING = "not_pending"
    # The body is not what the pending tool declared.
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
        """An answer from a client that knows only which tool it is answering
        — a chat, whose pin says nothing about what asked for it."""
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
