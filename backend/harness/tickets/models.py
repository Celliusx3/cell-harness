"""What a ticket is, and the file that keeps every bot's tickets."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TicketState = Literal["working", "done", "failed"]


class Ticket(BaseModel):
    """One task a bot handed to a worker: whose, its title and task, and how far it has got."""

    model_config = ConfigDict(frozen=True)

    id: str
    bot_id: str
    title: str
    task: str
    state: TicketState
    created_at: datetime


class TicketsFile(BaseModel):
    """The tickets file: every ticket, in the order started."""

    model_config = ConfigDict(frozen=True)

    tickets: tuple[Ticket, ...] = ()
