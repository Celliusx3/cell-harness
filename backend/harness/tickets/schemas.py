"""The tickets routes' response bodies."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from harness.session.models import SessionEvent
from harness.tickets.models import TicketState


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
