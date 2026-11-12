"""What `ticket_accept` and `ticket_report` are called with."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from harness.tickets.models import ReportState


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
