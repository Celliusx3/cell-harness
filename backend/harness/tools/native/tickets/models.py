"""What `ticket_route`, `ticket_report` and `ticket_note` are called with."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from harness.tickets.models import ReportState

TICKET_ID = "The id of one of your tickets."


class AcceptItem(BaseModel):
    """New work, handed to a worker on a new ticket."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["accept"]
    title: str = Field(
        min_length=1,
        description="A short name for the new ticket, at most eight words, that the user sees.",
    )
    task: str = Field(
        min_length=1,
        description=(
            "Everything the worker needs. The worker does not see this chat, so include what "
            "the user asked, in their words."
        ),
    )


class AttachItem(BaseModel):
    """The user's message for one of the bot's tickets."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["attach"]
    ticket: str = Field(min_length=1, description=TICKET_ID)
    text: str = Field(
        min_length=1, description="The user's message for that ticket, in their words."
    )


class StopItem(BaseModel):
    """A ticket the user asked to stop."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["stop"]
    ticket: str = Field(min_length=1, description=TICKET_ID)


class IgnoreItem(BaseModel):
    """A message that asks for no work."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["ignore"]
    reason: str = Field(
        min_length=1, description="Why the message asks for no work, in a few words."
    )


RouteItem = Annotated[AcceptItem | AttachItem | StopItem | IgnoreItem, Field(discriminator="kind")]


class TicketRouteArgs(BaseModel):
    """What the model passes to `ticket_route`."""

    model_config = ConfigDict(frozen=True)

    items: tuple[RouteItem, ...] = Field(
        min_length=1,
        max_length=20,
        description="One item for each request in the message, at most 20.",
    )


class TicketReportArgs(BaseModel):
    """What the worker passes to `ticket_report`."""

    model_config = ConfigDict(frozen=True)

    state: ReportState = Field(
        description=(
            "ready: the result is done. blocked: you cannot go on without the user. failed: the "
            "task cannot be done. dropped: there is nothing to do. waiting: you wait for "
            "something outside your tools. progress: a step worth recording, which tells nobody."
        )
    )
    summary: str = Field(
        min_length=1,
        description="What you did or found, in a few sentences, for the orchestrator.",
    )
    question: str | None = Field(
        default=None,
        description=(
            "One concrete question for the user, only with the state blocked or waiting. It "
            "reaches the user unchanged."
        ),
    )


class TicketNoteArgs(BaseModel):
    """What the bot passes to `ticket_note`."""

    model_config = ConfigDict(frozen=True)

    ticket: str = Field(
        min_length=1, description="The id of one of your tickets, as ticket_route returned it."
    )
    text: str = Field(min_length=1, description="The fact, in at most 100 words.")
