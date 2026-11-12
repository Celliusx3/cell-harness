"""What a ticket is, and the file that keeps every bot's tickets."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from harness.session.heard import ReportState as ReportState

TicketState = Literal[
    "queued",
    "working",
    "waiting",
    "needs_answer",
    "blocked",
    "failed",
    "done",
    "dropped",
    "stopped",
]


class TicketNotFound(LookupError):
    """No ticket has this id."""


class TicketNotAsking(RuntimeError):
    """The ticket asks no question now, so it has nothing to answer."""


NEEDS_YOU: frozenset[TicketState] = frozenset({"needs_answer", "blocked", "failed"})
RETRYABLE: frozenset[TicketState] = frozenset({"blocked", "failed"})


class TicketNotRetryable(RuntimeError):
    """Only a blocked or failed ticket can be tried again."""


class TicketStopped(RuntimeError):
    """The user stopped this ticket, so it takes nothing more."""


class Ticket(BaseModel):
    """One task a bot handed to a worker: whose, its title and task, and how far it has got."""

    model_config = ConfigDict(frozen=True)

    id: str
    bot_id: str
    title: str
    task: str
    state: TicketState
    created_at: datetime


def ticket_state(state: ReportState, question: str | None) -> TicketState:
    """The state a ticket takes from its worker's report; `progress` never ends a turn."""
    match state:
        case "ready":
            return "done"
        case "blocked" | "waiting" if question is not None:
            return "needs_answer"
        case "progress":
            raise ValueError("a progress report never ends a worker's turn")
        case _:
            return state


class TicketsFile(BaseModel):
    """The tickets file: every ticket, in the order started."""

    model_config = ConfigDict(frozen=True)

    tickets: tuple[Ticket, ...] = ()
