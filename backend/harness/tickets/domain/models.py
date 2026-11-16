"""What a ticket is, and the file that keeps every bot's tickets."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from harness.files.domain.models import ChatFile
from harness.secrets import Destination
from harness.session.domain.heard import ReportState as ReportState
from harness.tools.domain.decision import ApprovalMode

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


class TicketNotAskingError(RuntimeError):
    """The ticket asks no question now, so it has nothing to answer."""


NEEDS_YOU_STATES: frozenset[TicketState] = frozenset({"needs_answer", "blocked", "failed"})
RETRYABLE_STATES: frozenset[TicketState] = frozenset({"blocked", "failed"})
FINISHED_STATES: frozenset[TicketState] = frozenset({"done", "failed", "dropped"})


class UnretryableTicketError(RuntimeError):
    """Only a blocked or failed ticket can be tried again."""


class StoppedTicketError(RuntimeError):
    """The user stopped this ticket, so it takes nothing more."""


class Ticket(BaseModel):
    """One task a bot handed to a worker: whose, its title and task, its state, and its mode."""

    model_config = ConfigDict(frozen=True)

    id: str
    bot_id: str
    title: str
    task: str
    state: TicketState
    created_at: datetime
    mode: ApprovalMode = Field(
        default="ask", description="The chat's mode at accept; tickets saved before it ask."
    )
    files: tuple[ChatFile, ...] = Field(
        default=(), description="The files attached in the turn that accepted it; none before."
    )
    chat_id: str | None = Field(
        default=None, description="The chat it came from; none in tickets saved before it was kept."
    )


def ticket_chat_id(ticket: Ticket, *, chat_of: Callable[[str], str]) -> str:
    """The chat `ticket` came from; its bot's own chat, by `chat_of`, for one saved before."""
    return ticket.chat_id if ticket.chat_id is not None else chat_of(ticket.bot_id)


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


class AskedKey(BaseModel):
    """The key a ticket's question waits for: the bot it is granted to, its name, its one API."""

    model_config = ConfigDict(frozen=True)

    bot_id: str
    name: str
    destination: Destination
