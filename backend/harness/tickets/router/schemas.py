"""The tickets routes' request and response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness.secrets import SecretValue
from harness.session.models import SessionEvent
from harness.tickets.domain.models import TicketState
from harness.tools.models.decision import Approval, Denial


class TicketRow(BaseModel):
    """One ticket as a page lists it, its time in ISO UTC; its task stays with its worker."""

    model_config = ConfigDict(frozen=True)

    id: str
    bot_id: str
    title: str
    state: TicketState
    created_at: str


class TicketDetail(BaseModel):
    """One ticket, its worker's whole log, and whether its worker is still in flight."""

    model_config = ConfigDict(frozen=True)

    ticket: TicketRow
    events: list[SessionEvent]
    running: bool


class TicketAnswer(BaseModel):
    """The person's answer to a ticket's question."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)


class TicketSecret(BaseModel):
    """The key the person pasted for a ticket's question that asks for one."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    value: SecretValue


class TicketApproval(BaseModel):
    """The person's decision on the call a ticket's worker waits to have allowed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Approval | Denial = Field(discriminator="kind")
