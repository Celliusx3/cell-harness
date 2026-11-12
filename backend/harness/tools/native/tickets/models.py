"""What `ticket_accept` is called with."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TicketAcceptArgs(BaseModel):
    """What the model passes to `ticket_accept`."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(
        min_length=1,
        description="A short name for the ticket, at most eight words, that the user sees.",
    )
    task: str = Field(
        min_length=1,
        description=(
            "Everything the worker needs to do the task. The worker does not see this chat, so "
            "include what the user asked, in their words."
        ),
    )
